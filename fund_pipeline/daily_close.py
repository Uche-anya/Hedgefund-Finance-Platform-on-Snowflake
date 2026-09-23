"""Part 1: value a small, already-settled GBP portfolio from local files."""

import argparse
import csv
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from fund_pipeline.landing import verify_delivery


def read_rows(path, business_date):
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        raise ValueError(f"{path.name}: file has no records")
    for row in rows:
        if row["business_date"] != business_date:
            raise ValueError(f"{path.name}: expected business date {business_date}")
    return rows


def decimal_value(value):
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError(f"Expected a finite number, got {value!r}")
    return number


def calculate_close(folder, business_date):
    prices = {}
    for row in read_rows(folder / "prices.csv", business_date):
        instrument = row["instrument"]
        if instrument in prices:
            raise ValueError(f"Duplicate price for {instrument}")
        if row["currency"] != "GBP":
            raise ValueError("Part 1 only supports GBP prices")
        price = decimal_value(row["close_price"])
        if price <= 0:
            raise ValueError(f"Price must be positive for {instrument}")
        prices[instrument] = price

    holdings = []
    seen_positions = set()
    for row in read_rows(folder / "positions.csv", business_date):
        instrument = row["instrument"]
        key = (row["portfolio"], instrument)
        if key in seen_positions:
            raise ValueError(f"Duplicate position for {key}")
        seen_positions.add(key)
        if instrument not in prices:
            raise ValueError(f"Missing price for {instrument}; close stopped")

        quantity = decimal_value(row["quantity"])
        holdings.append({
            "portfolio": row["portfolio"],
            "instrument": instrument,
            "market_value": quantity * prices[instrument],
        })

    cash_rows = read_rows(folder / "cash.csv", business_date)
    if len(cash_rows) != 1 or cash_rows[0]["currency"] != "GBP":
        raise ValueError("Part 1 expects exactly one GBP fund cash balance")
    cash = decimal_value(cash_rows[0]["balance"])
    equity_value = sum((row["market_value"] for row in holdings), Decimal("0"))
    return {"holdings": holdings, "cash": cash, "nav": cash + equity_value}


def pounds(value):
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ",.2f")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", required=True, type=date.fromisoformat)
    parser.add_argument("--delivery", type=Path, help="Use a saved delivery instead of fixtures")
    args = parser.parse_args()
    business_date = args.business_date.isoformat()
    folder = args.delivery or Path(__file__).resolve().parents[1] / "fixtures" / business_date
    if args.delivery:
        manifest = verify_delivery(folder, business_date)
        print(f"Input delivery: {manifest['delivery_id']}")
    result = calculate_close(folder, business_date)

    print(f"Northbridge local valuation | {business_date} | GBP | NOT APPROVED")
    for row in result["holdings"]:
        print(f"{row['portfolio']} / {row['instrument']}: {pounds(row['market_value'])}")
    print(f"Cash: {pounds(result['cash'])}")
    print(f"Fund NAV: {pounds(result['nav'])}")


if __name__ == "__main__":
    main()
