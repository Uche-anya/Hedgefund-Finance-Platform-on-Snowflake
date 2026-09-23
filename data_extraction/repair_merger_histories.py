"""Repair CHK/EXE and EQR/VMRK histories using reviewed merger evidence."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import time
from uuid import uuid4

from data_extraction.check_bny_identity import read_identity
from data_extraction.check_ticker_changes import compare_pair
from data_extraction.historical_prices import fetch, inspect_bars, write_json
from data_extraction.repair_bny_history import bar_date, checked_file


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/historical_prices/a7f9a9e28bf3430c97e6a776bcdafba9"
REFERENCES = ROOT / "data/reference_checks/db78b7c287e646b8867efab11d4a6555"
EXE_NOTICE = "https://investors.expandenergy.com/news-releases/news-release-details/chesapeake-energy-and-southwestern-energy-complete-merger-and"
PAIRS = (
    ("CHK", "EXE", "2024-10-01", "2024-10-02", "XNAS", "XNAS"),
    ("EQR", "VMRK", "2026-08-17", "2026-08-18", "XNYS", "XNYS"),
)
# Internal ID, share-class FIGI, composite FIGI, issuer CIK from saved evidence.
IDENTITIES = {
    "EXE": ("US_EXPAND_ENERGY_COMMON", "BBG00Z6DX607", "BBG00Z6DX554", "895126"),
    "VMRK": ("US_VIVMARK_COMMON", "BBG001S723L9", "BBG000BG8M31", "906107"),
}


def approve_identity(pair, before, after):
    old, new, old_day, new_day, old_exchange, new_exchange = pair
    instrument, share_figi, composite_figi, cik = IDENTITIES[new]
    for label, row in (("old", before), ("new", after)):
        if row["share_class_figi"] != share_figi or row["composite_figi"] != composite_figi:
            raise ValueError(f"{new}: {label} identifiers differ from reviewed evidence")
        actual_cik = str(row.get("cik") or "").strip().lstrip("0")
        if actual_cik != cik:
            if not (new == "EXE" and label == "new" and not actual_cik):
                raise ValueError(f"{new}: {label} CIK differs from reviewed evidence")
    status, notes = compare_pair(before, after, old_exchange, new_exchange)
    if status == "IDENTIFIERS_MATCH":
        return "Identifiers match reviewed reference observations"
    # This exception is only for the known missing EXE CIK, not other fields.
    if (new == "EXE" and status == "REVIEW_MISSING" and notes == "Missing fields: cik"
            and not str(after.get("cik") or "").strip()):
        return ("Accepted missing new CIK: matching share-class/composite FIGIs; "
                "Issuer confirms Chesapeake renamed Expand Energy and CHK became EXE. "
                "Raw CIK remains missing. Source: " + EXE_NOTICE)
    raise ValueError(f"{old} -> {new}: {notes}")


def check_references(folder):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    requests = {(r["ticker"], r["date"]): r for r in manifest["requests"]}
    evidence, decisions = {}, {}
    for pair in PAIRS:
        old, new, old_day, new_day, _, _ = pair
        rows = []
        for ticker, day in ((old, old_day), (new, new_day)):
            filename = f"{ticker}_{day}.json"
            payload = checked_file(folder / filename, requests[(ticker, day)]["sha256"])
            rows.append(read_identity(payload, ticker, day))
            evidence[filename] = payload
        decisions[new] = approve_identity(pair, rows[0], rows[1])
    return evidence, decisions


def combine_prices(pair, old_payload, new_payload, peer_payload, start, end):
    old, new, old_day, new_day, _, _ = pair
    inspect_bars(old_payload, old, start, old_day)
    inspect_bars(new_payload, new, start, end)
    inspect_bars(peer_payload, "AAPL", start, end)
    instrument, figi, _, _ = IDENTITIES[new]
    prices = {}
    for ticker, payload in ((old, old_payload), (new, new_payload)):
        for bar in json.loads(payload, parse_float=Decimal)["results"]:
            day = bar_date(bar)
            if ticker == new and day < new_day:
                continue
            if day in prices:
                raise ValueError(f"{new}: duplicate price date {day}")
            prices[day] = {
                "valuation_date": day, "instrument_id": instrument,
                "share_class_figi": figi, "source_ticker": ticker, "currency": "USD",
                "open": str(bar["o"]), "high": str(bar["h"]),
                "low": str(bar["l"]), "close_price": str(bar["c"]),
                "volume": str(bar["v"]), "price_basis": "unadjusted",
            }
    peer_dates = {bar_date(bar) for bar in json.loads(peer_payload)["results"]}
    missing = sorted(peer_dates - prices.keys())
    extra = sorted(prices.keys() - peer_dates)
    if missing or extra:
        raise ValueError(f"{new}: dates differ from AAPL. Missing: {missing}; extra: {extra}")
    return [prices[day] for day in sorted(prices)]


def repair(snapshot, references, root, key):
    if not key.strip():
        raise ValueError("An API key is required")
    evidence, decisions = check_references(references)
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    start, end = manifest["requested_from"], manifest["requested_to"]
    peer = checked_file(snapshot / "AAPL.json", manifest["files"]["AAPL.json"]["sha256"])
    inputs = {}
    for old, new, old_day, new_day, _, _ in PAIRS:
        if not start <= old_day < new_day <= end:
            raise ValueError(f"Snapshot does not span the {new} change")
        inputs[new] = checked_file(snapshot / f"{new}.json", manifest["files"][f"{new}.json"]["sha256"])

    folder = root / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    print(f"Repair folder: {folder}", flush=True)
    (folder / "AAPL_coverage_reference.json").write_bytes(peer)
    for filename, payload in evidence.items():
        (folder / filename).write_bytes(payload)
    write_json(folder / "identity_decisions.json", decisions)
    results = []
    for index, pair in enumerate(PAIRS):
        old, new, old_day, new_day, _, _ = pair
        if index:
            time.sleep(13)
        print(f"Requesting {old}: {start} through {old_day}", flush=True)
        payload = fetch(old, key, start, old_day)
        received_at = datetime.now(timezone.utc).isoformat()
        (folder / f"{old}.json").write_bytes(payload)
        (folder / f"{new}_original.json").write_bytes(inputs[new])
        rows = combine_prices(pair, payload, inputs[new], peer, start, end)
        filename = f"{new}_prices.csv"
        with (folder / filename).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        results.append({
            "ticker": new, "file": filename, "row_count": len(rows),
            "received_at_utc": received_at, "identity_decision": decisions[new],
            "mapping": [{"ticker": old, "from": start, "to": old_day},
                        {"ticker": new, "from": new_day, "to": end}],
        })
        print(f"{old} -> {new}: saved {len(rows)} rows; dates match AAPL", flush=True)

    output = {
        "source_system": "massive", "original_snapshot": str(snapshot),
        "reference_snapshot": str(references), "requested_from": start, "requested_to": end,
        "repairs": results, "coverage_check": "Saved AAPL dates; independent calendar check pending",
        "identity_check": "Two dated observations per pair; not daily identity verification",
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()},
    }
    write_json(folder / "manifest.json", output)
    print(f"Both repairs complete: {folder}")
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--references", type=Path, default=REFERENCES)
    args = parser.parse_args()
    key = os.environ.get("MASSIVE_API_KEY") or getpass("Massive API key (hidden): ")
    try:
        repair(args.snapshot, args.references, ROOT / "data/price_repairs", key)
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        raise SystemExit(f"Repair stopped: {error}. Without manifest.json the batch is incomplete.") from None


if __name__ == "__main__":
    main()
