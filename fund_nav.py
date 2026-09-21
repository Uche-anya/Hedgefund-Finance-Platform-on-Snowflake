"""Part 5: value trade-derived holdings and include settled and outstanding cash."""

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from cash_settlement import calculate_cash
from daily_close import pounds
from landing import verify_delivery


def read_closing_prices(path, as_of, currency="GBP"):
    prices = {}
    seen = set()
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != ["valuation_date", "instrument", "currency", "close_price"]:
            raise ValueError("Unexpected closing price columns")
        for row in reader:
            if None in row or any(value is None or not value.strip() for value in row.values()):
                raise ValueError("Blank field or malformed closing price record")
            price_date = date.fromisoformat(row["valuation_date"]).isoformat()
            key = (price_date, row["instrument"])
            if key in seen:
                raise ValueError(f"Duplicate closing price for {key}")
            seen.add(key)
            if row["currency"] != currency:
                raise ValueError(f"Expected {currency} closing prices")
            try:
                price = Decimal(row["close_price"])
            except InvalidOperation as error:
                raise ValueError("Invalid closing price") from error
            if not price.is_finite() or price <= 0:
                raise ValueError("Closing price must be finite and positive")
            if price_date == as_of:
                prices[row["instrument"]] = price
    return prices


def calculate_nav(folder, business_date, as_of, currency="GBP"):
    as_of = date.fromisoformat(as_of).isoformat()
    balances = calculate_cash(folder, business_date, as_of, currency)
    prices = read_closing_prices(folder / "closing_prices.csv", as_of, currency)
    holdings = []
    long_assets = Decimal("0")
    short_obligations = Decimal("0")

    for position in balances["positions"]:
        instrument = position["instrument"]
        quantity = position["quantity"]
        if quantity == 0:
            market_value = Decimal("0")
        else:
            if instrument not in prices:
                raise ValueError(f"Missing closing price for {instrument} on {as_of}; NAV stopped")
            market_value = quantity * prices[instrument]
        holdings.append({**position, "market_value": market_value})
        if market_value >= 0:
            long_assets += market_value
        else:
            # Show what we owe as a positive amount, then subtract it once.
            short_obligations -= market_value

    nav = (balances["cash"] + balances["receivables"] - balances["payables"]
           + long_assets - short_obligations)
    return {
        "currency": currency,
        "cash": balances["cash"],
        "receivables": balances["receivables"],
        "payables": balances["payables"],
        "obligations": balances["obligations"],
        "holdings": holdings,
        "long_assets": long_assets,
        "short_obligations": short_obligations,
        "nav": nav,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", required=True, type=date.fromisoformat)
    parser.add_argument("--as-of", required=True, type=date.fromisoformat)
    parser.add_argument("--delivery", required=True, type=Path)
    parser.add_argument("--currency", choices=("GBP", "USD"), default="GBP")
    args = parser.parse_args()
    business_date, as_of = args.business_date.isoformat(), args.as_of.isoformat()
    manifest = verify_delivery(args.delivery, business_date, bundle="nav")
    result = calculate_nav(args.delivery, business_date, as_of, args.currency)
    print(f"Input delivery: {manifest['delivery_id']}")
    print(f"Fund NAV | {as_of} | trade batch {business_date} | {args.currency} | NOT APPROVED")
    for holding in result["holdings"]:
        print(f"{holding['portfolio']} / {holding['instrument']}: "
              f"{holding['quantity']} shares, signed value {pounds(holding['market_value'])}")
    print(f"Settled cash: {pounds(result['cash'])}")
    print(f"Add receivables: {pounds(result['receivables'])}")
    print(f"Subtract payables: {pounds(result['payables'])}")
    print(f"Add long share assets: {pounds(result['long_assets'])}")
    print(f"Subtract short share obligations: {pounds(result['short_obligations'])}")
    print(f"Fund NAV: {pounds(result['nav'])}")
    for obligation in result["obligations"]:
        print(f"{obligation['execution_id']}: {obligation['type']} "
              f"{pounds(obligation['amount'])}, due {obligation['due']}, {obligation['status']}")


if __name__ == "__main__":
    main()
