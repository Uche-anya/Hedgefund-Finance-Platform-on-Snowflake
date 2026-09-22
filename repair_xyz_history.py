"""Join Block's SQ and XYZ prices using the verified ticker-change dates."""

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from check_bny_identity import read_identity
from check_xyz_identity import CHECKS
from historical_prices import fetch, inspect_bars, write_json
from repair_bny_history import bar_date, checked_file


ROOT = Path(__file__).resolve().parent
SNAPSHOT = ROOT / "data/historical_prices/a7f9a9e28bf3430c97e6a776bcdafba9"
REFERENCES = ROOT / "data/reference_checks/4c6f68fe8a90417f96a22d7bc5cd726f"
CHANGE_DATE = "2025-01-21"
LAST_SQ_DATE = "2025-01-20"
BLOCK_FIGI = "BBG001TFLWL5"


def check_references(folder):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    requests = {(r["ticker"], r["date"]): r for r in manifest["requests"]}
    evidence = {}
    for ticker, day in CHECKS:
        filename = f"{ticker}_{day}.json"
        payload = checked_file(folder / filename, requests[(ticker, day)]["sha256"])
        row = read_identity(payload, ticker, day)
        if (row["share_class_figi"] != BLOCK_FIGI
                or row["composite_figi"] != "BBG0018SLC07"
                or row["cik"].lstrip("0") != "1512673"
                or row["type"] != "CS" or row["primary_exchange"] != "XNYS"
                or row["currency_name"] != "usd"):
            raise ValueError(f"{ticker} on {day}: Block identity checks failed")
        evidence[filename] = payload
    return evidence


def combine_prices(sq_payload, xyz_payload, peer_payload, start, end):
    inspect_bars(sq_payload, "SQ", start, LAST_SQ_DATE)
    inspect_bars(xyz_payload, "XYZ", start, end)
    inspect_bars(peer_payload, "AAPL", start, end)
    prices = {}
    for ticker, payload in (("SQ", sq_payload), ("XYZ", xyz_payload)):
        for bar in json.loads(payload, parse_float=Decimal)["results"]:
            day = bar_date(bar)
            if ticker == "XYZ" and day < CHANGE_DATE:
                continue
            if day in prices:
                raise ValueError(f"Duplicate Block price date: {day}")
            prices[day] = {
                "valuation_date": day,
                "instrument_id": "US_BLOCK_CLASS_A",
                "share_class_figi": BLOCK_FIGI,
                "source_ticker": ticker,
                "currency": "USD",
                "open": str(bar["o"]),
                "high": str(bar["h"]),
                "low": str(bar["l"]),
                "close_price": str(bar["c"]),
                "volume": str(bar["v"]),
                "price_basis": "unadjusted",
            }
    peer_dates = {bar_date(bar) for bar in json.loads(peer_payload)["results"]}
    missing = sorted(peer_dates - prices.keys())
    extra = sorted(prices.keys() - peer_dates)
    if missing or extra:
        raise ValueError(f"Dates differ from saved AAPL history. Missing: {missing}; extra: {extra}")
    return [prices[day] for day in sorted(prices)]


def repair(snapshot, references, root, key):
    if not key.strip():
        raise ValueError("An API key is required")
    evidence = check_references(references)
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    start, end = manifest["requested_from"], manifest["requested_to"]
    if not start < CHANGE_DATE <= end:
        raise ValueError("Snapshot must span the ticker change")
    xyz = checked_file(snapshot / "XYZ.json", manifest["files"]["XYZ.json"]["sha256"])
    peer = checked_file(snapshot / "AAPL.json", manifest["files"]["AAPL.json"]["sha256"])

    folder = root / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    print(f"Repair evidence folder: {folder}", flush=True)
    print(f"Requesting SQ: {start} through {LAST_SQ_DATE}", flush=True)
    sq = fetch("SQ", key, start, LAST_SQ_DATE)
    received_at = datetime.now(timezone.utc).isoformat()
    (folder / "SQ.json").write_bytes(sq)
    (folder / "XYZ_original.json").write_bytes(xyz)
    (folder / "AAPL_coverage_reference.json").write_bytes(peer)
    for filename, payload in evidence.items():
        (folder / filename).write_bytes(payload)

    rows = combine_prices(sq, xyz, peer, start, end)
    with (folder / "block_prices.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    output = {
        "source_system": "massive",
        "original_snapshot": str(snapshot),
        "reference_snapshot": str(references),
        "requested_from": start,
        "requested_to": end,
        "sq_received_at_utc": received_at,
        "instrument_id": "US_BLOCK_CLASS_A",
        "share_class_figi": BLOCK_FIGI,
        "row_count": len(rows),
        "first_date": rows[0]["valuation_date"],
        "last_date": rows[-1]["valuation_date"],
        "mapping": [
            {"ticker": "SQ", "from": start, "to": LAST_SQ_DATE},
            {"ticker": "XYZ", "from": CHANGE_DATE, "to": end},
        ],
        "coverage_check": "Matches saved AAPL dates; not an independent exchange calendar check",
        "identity_check": "Two saved dated reference observations; not daily identity verification",
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()},
    }
    write_json(folder / "manifest.json", output)
    print(f"Saved {len(rows)} Block price rows. No duplicate dates or gaps against AAPL.")
    print(f"Corrected dataset: {folder / 'block_prices.csv'}")
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
        raise SystemExit(f"Repair stopped: {error}. A complete repair requires manifest.json.") from None


if __name__ == "__main__":
    main()
