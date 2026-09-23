"""Assemble the saved September price snapshot and its eight reviewed repairs."""

import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
from uuid import uuid4

from data_extraction.historical_prices import inspect_bars, write_json
from data_extraction.repair_bny_history import bar_date, checked_file


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/historical_prices/a7f9a9e28bf3430c97e6a776bcdafba9"
REPAIRS = {
    "BNY": ("f978b4aac9584f1da97870318dcc6b98", "bank_prices.csv"),
    "XYZ": ("e391cf0dcbf142978deacc40d77211ba", "block_prices.csv"),
    "ECHO": ("0f1d760ceb80466eb129665af599dd2d", "ECHO_prices.csv"),
    "P": ("0f1d760ceb80466eb129665af599dd2d", "P_prices.csv"),
    "FISV": ("0f1d760ceb80466eb129665af599dd2d", "FISV_prices.csv"),
    "MRSH": ("0f1d760ceb80466eb129665af599dd2d", "MRSH_prices.csv"),
    "EXE": ("a3d7d54cebdc41d6a5d700d67fa72f84", "EXE_prices.csv"),
    "VMRK": ("a3d7d54cebdc41d6a5d700d67fa72f84", "VMRK_prices.csv"),
}
SHORT_STARTS = {
    "FDXF": "2026-06-01", "HONA": "2026-06-29", "PSKY": "2025-08-07",
    "Q": "2025-11-03", "SNDK": "2025-02-24",
}
FIELDS = (
    "valuation_date", "universe_ticker", "instrument_id", "share_class_figi",
    "source_ticker", "currency", "open", "high", "low", "close_price", "volume",
    "price_basis", "identity_status", "source_system", "input_file", "input_row_number",
)


def validate_rows(ticker, rows, expected_dates):
    dates = [r["valuation_date"] for r in rows]
    if dates != sorted(set(dates)):
        raise ValueError(f"{ticker}: duplicate or unordered dates")
    if dates != expected_dates:
        missing = sorted(set(expected_dates) - set(dates))
        extra = sorted(set(dates) - set(expected_dates))
        raise ValueError(f"{ticker}: coverage differs; missing {missing}, extra {extra}")
    for row in rows:
        numbers = [Decimal(row[f]) for f in ("open", "high", "low", "close_price", "volume")]
        if not all(n.is_finite() for n in numbers):
            raise ValueError(f"{ticker}: non-finite number")
        opening, high, low, close, volume = numbers
        if low <= 0 or not low <= opening <= high or not low <= close <= high or volume < 0:
            raise ValueError(f"{ticker}: invalid daily prices or volume")
        if row["currency"] != "USD" or row["price_basis"] != "unadjusted":
            raise ValueError(f"{ticker}: unexpected currency or price basis")


def validate_mapping(rows, mapping):
    for row in rows:
        matches = [m for m in mapping if m["from"] <= row["valuation_date"] <= m["to"]]
        if len(matches) != 1 or matches[0]["ticker"] != row["source_ticker"]:
            raise ValueError("Repair row does not match its dated ticker mapping")
    for field in ("instrument_id", "share_class_figi"):
        values = {r[field] for r in rows}
        if len(values) != 1 or not next(iter(values), ""):
            raise ValueError(f"Repair has missing or inconsistent {field}")


def assemble():
    inputs = {}

    def read_file(path, expected_hash=None):
        payload = checked_file(path, expected_hash) if expected_hash else path.read_bytes()
        inputs[path.relative_to(ROOT).as_posix()] = hashlib.sha256(payload).hexdigest()
        return payload

    manifest = json.loads(read_file(SNAPSHOT / "manifest.json"))
    start, end = manifest["requested_from"], manifest["requested_to"]
    symbols = manifest["symbols"]
    if len(symbols) != 503 or len(set(symbols)) != len(symbols):
        raise ValueError("Expected 503 distinct tickers in this saved snapshot")
    if not (REPAIRS.keys() | SHORT_STARTS.keys()) <= set(symbols):
        raise ValueError("Reviewed tickers are missing from the snapshot")

    peer = read_file(SNAPSHOT / "AAPL.json", manifest["files"]["AAPL.json"]["sha256"])
    inspect_bars(peer, "AAPL", start, end)
    peer_dates = [bar_date(b) for b in json.loads(peer)["results"]]
    batches = {}
    for batch, _ in REPAIRS.values():
        if batch in batches:
            continue
        folder = ROOT / "data/price_repairs" / batch
        saved = json.loads(read_file(folder / "manifest.json"))
        if (Path(saved["original_snapshot"]).resolve() != SNAPSHOT.resolve()
                or saved["requested_from"] != start or saved["requested_to"] != end):
            raise ValueError(f"Repair {batch} belongs to another snapshot or date range")
        # Check the full evidence bundle, not just the finished CSV.
        for filename, digest in saved["sha256"].items():
            read_file(folder / filename, digest)
        batches[batch] = saved

    all_rows, coverage = [], []
    original_count, replaced_count = 0, 0
    for ticker in sorted(symbols):
        original_file = SNAPSHOT / f"{ticker}.json"
        details = manifest["files"][original_file.name]
        payload = read_file(original_file, details["sha256"])
        stats = inspect_bars(payload, ticker, start, end)
        if any(stats[k] != details[k] for k in ("rows", "first_date", "last_date")):
            raise ValueError(f"{ticker}: original counts or dates disagree with manifest")
        original_count += stats["rows"]

        if ticker in REPAIRS:
            batch, filename = REPAIRS[ticker]
            saved = batches[batch]
            input_file = ROOT / "data/price_repairs" / batch / filename
            data = read_file(input_file, saved["sha256"][filename])
            rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
            decision = saved
            if "repairs" in saved:
                decision = next(r for r in saved["repairs"] if r["ticker"] == ticker)
                if decision["file"] != filename:
                    raise ValueError(f"{ticker}: repair filename disagrees with manifest")
            if len(rows) != decision["row_count"]:
                raise ValueError(f"{ticker}: repair row count disagrees with manifest")
            validate_mapping(rows, decision["mapping"])
            replaced_count += stats["rows"]
            identity_status = "reviewed_ticker_transition"
        else:
            input_file = original_file
            rows = []
            for bar in json.loads(payload, parse_float=Decimal)["results"]:
                rows.append({
                    "valuation_date": bar_date(bar), "instrument_id": "", "share_class_figi": "",
                    "source_ticker": ticker, "currency": "USD", "price_basis": "unadjusted",
                    "open": str(bar["o"]), "high": str(bar["h"]), "low": str(bar["l"]),
                    "close_price": str(bar["c"]), "volume": str(bar["v"]),
                })
            # A ticker is not a verified, permanent security identifier.
            identity_status = "provider_ticker_only"

        expected = [d for d in peer_dates if d >= SHORT_STARTS.get(ticker, start)]
        validate_rows(ticker, rows, expected)
        for number, row in enumerate(rows, 1):
            row.update(universe_ticker=ticker, identity_status=identity_status,
                       source_system="massive", input_file=input_file.relative_to(ROOT).as_posix(),
                       input_row_number=number)
        all_rows.extend(rows)
        coverage.append({
            "universe_ticker": ticker, "rows": len(rows), "original_rows": stats["rows"],
            "first_date": rows[0]["valuation_date"], "last_date": rows[-1]["valuation_date"],
            "repaired": ticker in REPAIRS, "expected_short_history": ticker in SHORT_STARTS,
            "missing_peer_dates": 0, "extra_peer_dates": 0, "identity_status": identity_status,
        })

    if original_count != manifest["row_count"]:
        raise ValueError("Original total row count disagrees with manifest")
    replacement_count = sum(c["rows"] for c in coverage if c["repaired"])
    if len(all_rows) != original_count - replaced_count + replacement_count:
        raise ValueError("Assembled row count does not reconcile")

    folder = ROOT / "data/assembled_prices" / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    for filename, rows, fields in (("prices.csv", all_rows, FIELDS),
                                   ("coverage.csv", coverage, list(coverage[0]))):
        with (folder / filename).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    write_json(folder / "manifest.json", {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_system": "massive", "requested_from": start, "requested_to": end,
        "ticker_count": len(symbols), "row_count": len(all_rows), "repair_count": len(REPAIRS),
        "original_row_count": original_count, "replaced_original_rows": replaced_count,
        "replacement_rows": replacement_count, "short_history_starts": SHORT_STARTS,
        "coverage_check": "AAPL peer dates; shorter histories checked from reviewed start dates",
        "independent_calendar_checked": False,
        "identity_note": "Eight reviewed transitions; other stable security IDs remain unverified and blank",
        "universe_note": "Snapshot membership, not historical index membership; survivorship bias applies",
        "price_note": "Unadjusted bars; corporate-action accounting is not implemented here",
        "row_number_note": "1-based CSV data row or JSON results array position, not physical file line",
        "input_sha256": inputs,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "output_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()},
    })
    print(f"Assembled {len(all_rows):,} rows across {len(symbols)} tickers.")
    print(f"Replaced {replaced_count:,} original rows with {replacement_count:,} repaired rows.")
    print("Eight repairs applied; five shorter histories retained. Coverage checks passed.")
    print(f"Saved dataset: {folder}")
    return folder


if __name__ == "__main__":
    assemble()
