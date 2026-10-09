"""Check the saved inputs for one business day before loading them."""

import argparse
import csv
import hashlib
import json
from pathlib import Path


def read_delivery(folder, file_name, date_field, business_date, scenario,
                  record_date_field=None):
    manifest_path = folder / "manifest.json"
    data_path = folder / file_name

    if not manifest_path.is_file() or not data_path.is_file():
        raise ValueError("Missing delivery in {}".format(folder))

    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)

    if manifest.get(date_field) != business_date:
        raise ValueError("Wrong date in {}".format(manifest_path))
    if manifest.get("scenario_id") != scenario:
        raise ValueError("Wrong scenario in {}".format(manifest_path))

    expected_hash = manifest.get("files", {}).get(file_name)
    actual_hash = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if expected_hash != actual_hash:
        raise ValueError("File changed after delivery: {}".format(data_path))

    with data_path.open(encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]

    if len(records) != manifest.get("record_count"):
        raise ValueError("Record count does not match {}".format(manifest_path))
    if not manifest.get("delivery_id"):
        raise ValueError("Missing delivery ID in {}".format(manifest_path))
    record_date_field = record_date_field or date_field
    for record in records:
        if record.get(record_date_field) != business_date or record.get("scenario_id") != scenario:
            raise ValueError("Record belongs to another day or scenario: {}".format(data_path))

    return manifest, records


def closing_prices(price_file, business_date, tickers):
    found = set()
    with price_file.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["valuation_date"] == business_date and row["universe_ticker"] in tickers:
                if row["close_price"] and row["currency"] == "USD":
                    found.add(row["universe_ticker"])
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date", help="YYYY-MM-DD")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()

    try:
        oms, trades = read_delivery(
            args.data_dir / "daily_oms" / args.scenario / args.business_date,
            "oms.jsonl", "business_date", args.business_date, args.scenario
        )
        settlement, settled = read_delivery(
            args.data_dir / "daily_settlements" / args.scenario / args.business_date,
            "settlements.jsonl", "settlement_date", args.business_date, args.scenario
        )
        tickers = {trade["market_ticker"] for trade in trades}
        priced = closing_prices(args.prices, args.business_date, tickers)
        if priced != tickers:
            raise ValueError("Missing closing prices: {}".format(", ".join(sorted(tickers - priced))))
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.exit(1, "Not ready: {}\n".format(error))

    print("Ready for {}".format(args.business_date))
    print("OMS: {} trades ({})".format(len(trades), oms["delivery_id"]))
    print("Settlements: {} confirmations ({})".format(len(settled), settlement["delivery_id"]))
    print("Closing prices: {} traded stocks covered".format(len(priced)))


if __name__ == "__main__":
    main()
