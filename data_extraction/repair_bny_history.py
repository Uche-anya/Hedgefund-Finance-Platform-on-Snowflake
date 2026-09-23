"""Build a separate price history for Bank of New York Mellon."""

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
from zoneinfo import ZoneInfo

from data_extraction.check_bny_identity import CHECKS, read_identity
from data_extraction.historical_prices import fetch, inspect_bars, write_json


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/historical_prices/a7f9a9e28bf3430c97e6a776bcdafba9"
REFERENCES = ROOT / "data/reference_checks/231d755172174a4b877e1818bae14383"
CHANGE_DATE = "2026-05-21"
LAST_BK_DATE = "2026-05-20"
BANK_FIGI = "BBG001S5P6Q6"


def checked_file(path, expected_hash):
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != expected_hash:
        raise ValueError(f"File fingerprint changed: {path.name}")
    return payload


def check_references(folder):
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    requests = {(r["ticker"], r["date"]): r for r in manifest["requests"]}
    evidence = {}
    for ticker, day in CHECKS:
        filename = f"{ticker}_{day}.json"
        record = requests[(ticker, day)]
        payload = checked_file(folder / filename, record["sha256"])
        row = read_identity(payload, ticker, day)
        if ticker == "BNY" and day < CHANGE_DATE:
            if row["share_class_figi"] != "BBG001SFL1C4" or row["type"] != "FUND":
                raise ValueError("Earlier BNY reference no longer matches the BlackRock fund")
        else:
            if (row["share_class_figi"] != BANK_FIGI
                    or row["composite_figi"] != "BBG000BD8PN9"
                    or row["type"] != "CS" or row["primary_exchange"] != "XNYS"
                    or row["currency_name"] != "usd"):
                raise ValueError(f"{ticker} on {day}: bank identity checks failed")
            if row["cik"] and row["cik"].lstrip("0") != "1390777":
                raise ValueError("Conflicting bank CIK")
        evidence[filename] = payload
    return evidence


def bar_date(bar):
    timestamp = datetime.fromtimestamp(bar["t"] / 1000, timezone.utc)
    return timestamp.astimezone(ZoneInfo("America/New_York")).date().isoformat()


def combine_prices(bk_payload, bny_payload, peer_payload, start, end):
    inspect_bars(bk_payload, "BK", start, LAST_BK_DATE)
    inspect_bars(bny_payload, "BNY", start, end)
    inspect_bars(peer_payload, "AAPL", start, end)
    prices = {}
    for ticker, payload in (("BK", bk_payload), ("BNY", bny_payload)):
        for bar in json.loads(payload, parse_float=Decimal)["results"]:
            day = bar_date(bar)
            # The old BNY fund must never enter the bank's price history.
            if ticker == "BNY" and day < CHANGE_DATE:
                continue
            if day in prices:
                raise ValueError(f"Duplicate bank price date: {day}")
            prices[day] = {
                "valuation_date": day,
                "instrument_id": "US_BNY_MELLON_COMMON",
                "share_class_figi": BANK_FIGI,
                "source_ticker": ticker,
                "currency": "USD",
                "open": str(bar["o"]), "high": str(bar["h"]),
                "low": str(bar["l"]), "close_price": str(bar["c"]),
                "volume": str(bar["v"]), "price_basis": "unadjusted",
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
    bny = checked_file(snapshot / "BNY.json", manifest["files"]["BNY.json"]["sha256"])
    peer = checked_file(snapshot / "AAPL.json", manifest["files"]["AAPL.json"]["sha256"])

    folder = root / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    print(f"Repair evidence folder: {folder}", flush=True)
    print(f"Requesting BK: {start} through {LAST_BK_DATE}", flush=True)
    bk = fetch("BK", key, start, LAST_BK_DATE)
    received_at = datetime.now(timezone.utc).isoformat()
    (folder / "BK.json").write_bytes(bk)
    (folder / "BNY_original.json").write_bytes(bny)
    (folder / "AAPL_coverage_reference.json").write_bytes(peer)
    for filename, payload in evidence.items():
        (folder / filename).write_bytes(payload)

    rows = combine_prices(bk, bny, peer, start, end)
    with (folder / "bank_prices.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    output = {
        "source_system": "massive", "original_snapshot": str(snapshot),
        "reference_snapshot": str(references), "requested_from": start, "requested_to": end,
        "bk_received_at_utc": received_at, "instrument_id": "US_BNY_MELLON_COMMON",
        "share_class_figi": BANK_FIGI, "row_count": len(rows),
        "first_date": rows[0]["valuation_date"], "last_date": rows[-1]["valuation_date"],
        "mapping": [{"ticker": "BK", "from": start, "to": LAST_BK_DATE},
                    {"ticker": "BNY", "from": CHANGE_DATE, "to": end}],
        "coverage_check": "Matches saved AAPL dates; not an independent exchange calendar check",
        "identity_check": "Four saved dated reference observations; not daily identity verification",
        "sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()},
    }
    write_json(folder / "manifest.json", output)
    print(f"Saved {len(rows)} bank price rows. No duplicate dates or gaps against AAPL.")
    print(f"Corrected dataset: {folder / 'bank_prices.csv'}")
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
