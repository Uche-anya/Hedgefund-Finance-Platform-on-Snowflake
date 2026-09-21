"""Carry a published day's holdings into the next weekday's trades."""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from build_positions import build_positions
from business_calendar import calendar_policy, validate_close_dates
from landing import verify_delivery
from publication import current, now


def carry_positions(database, previous_date, trade_folder, business_date, calendar=None):
    previous, today = validate_close_dates(previous_date, business_date, calendar)
    if not database.is_file():
        raise ValueError("Opening publication database does not exist")
    opening = current(database, previous.isoformat())
    manifest = verify_delivery(trade_folder, today.isoformat(), "trades")
    trades = build_positions(trade_folder, today.isoformat())

    quantities = {}
    for row in opening["close"]["holdings"]:
        key = (row["portfolio"], row["instrument"])
        if key in quantities:
            raise ValueError(f"Duplicate opening holding: {key}")
        quantity = Decimal(row["quantity"])
        if not quantity.is_finite():
            raise ValueError(f"Non-finite opening quantity: {key}")
        quantities[key] = quantity
    changes = {(row["portfolio"], row["instrument"]): row["quantity"]
               for row in trades["positions"]}
    positions = []
    for portfolio, instrument in sorted(quantities.keys() | changes.keys()):
        key = (portfolio, instrument)
        start = quantities.get(key, Decimal("0"))
        change = changes.get(key, Decimal("0"))
        positions.append({"portfolio": portfolio, "instrument": instrument,
                          "opening_quantity": start, "trade_change": change,
                          "closing_quantity": start + change})
    return {"run_id": uuid4().hex, "created_at": now(), "business_date": today.isoformat(),
            "status": "HOLDINGS ONLY - NOT APPROVED", "opening_date": previous.isoformat(),
            "calendar_policy": calendar_policy(calendar), "calendar": calendar,
            "opening_database": str(database.resolve()), "opening_publication": opening["publication"],
            "trade_delivery": str(trade_folder.resolve()), "trade_delivery_id": manifest["delivery_id"],
            "trade_manifest_sha256": hashlib.sha256((trade_folder / "manifest.json").read_bytes()).hexdigest(),
            "positions": positions, "repeated_executions": trades["repeated_executions"],
            "repeated_allocations": trades["repeated_allocations"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--previous-date", required=True)
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    args = parser.parse_args()
    report = carry_positions(args.database, args.previous_date, args.delivery, args.business_date)
    folder = Path(__file__).resolve().parent / "data" / "positions"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{report['run_id']}.json"
    temporary = output.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2, default=str)
        file.write("\n")
    temporary.rename(output)
    print(f"{report['business_date']} | {report['status']}")
    print(f"Opening close: {report['opening_date']}, published version {report['opening_publication']['version']}")
    for row in report["positions"]:
        print(f"{row['portfolio']} / {row['instrument']}: "
              f"{row['opening_quantity']} + ({row['trade_change']}) = {row['closing_quantity']} shares")
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
