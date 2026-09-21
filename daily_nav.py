"""Value next-day holdings and cash using explicitly selected closing prices."""

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from build_positions import build_positions
from carry_cash import carry_cash
from daily_close import pounds
from fund_nav import read_closing_prices
from landing import verify_delivery
from publication import show


def daily_nav(database, previous_date, activity, price_folder, business_date, calendar=None):
    verify_delivery(price_folder, business_date, "daily_prices")
    report = carry_cash(database, previous_date, activity, business_date, calendar)
    # Pin holdings to the exact publication used for opening cash. Do not ask
    # for 'current' again: another version could have been published meanwhile.
    candidate_id = report["opening_publication"]["candidate_id"]
    opening_report = show(database, candidate_id)["candidate"]["reconciliation"]
    opening = opening_report.get("local_close", opening_report["close"])
    balances = report["cash_close"]
    prices = read_closing_prices(price_folder / "closing_prices.csv", business_date, balances["currency"])
    quantities = {}
    for row in opening["holdings"]:
        key = (row["portfolio"], row["instrument"])
        quantity = Decimal(row["quantity"])
        if key in quantities or not quantity.is_finite():
            raise ValueError("Duplicate or non-finite opening holding")
        quantities[key] = quantity
    changes = {(row["portfolio"], row["instrument"]): row["quantity"]
               for row in build_positions(activity, business_date)["positions"]}
    holdings = []
    long_assets, short_obligations = Decimal(0), Decimal(0)
    for key in sorted(quantities.keys() | changes.keys()):
        start = quantities.get(key, Decimal(0))
        change = changes.get(key, Decimal(0))
        quantity = start + change
        price = prices.get(key[1])
        if quantity and price is None:
            raise ValueError(f"Missing closing price for {key[1]} on {business_date}; NAV stopped")
        value = quantity * price if quantity else Decimal(0)
        holdings.append({"portfolio": key[0], "instrument": key[1], "opening_quantity": start,
                         "trade_change": change, "quantity": quantity, "close_price": price,
                         "market_value": value})
        if value >= 0:
            long_assets += value
        else:
            short_obligations -= value
    close = {**balances, "holdings": holdings, "long_assets": long_assets,
             "short_obligations": short_obligations,
             "nav": balances["net_cash_and_obligations"] + long_assets - short_obligations}
    report.update(status="DAILY NAV - NOT RECONCILED OR APPROVED", close=close,
                  price_delivery=str(price_folder.resolve()),
                  price_manifest_sha256=hashlib.sha256((price_folder / "manifest.json").read_bytes()).hexdigest())
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--previous-date", required=True)
    parser.add_argument("--business-date", required=True)
    parser.add_argument("--delivery", type=Path, required=True)
    parser.add_argument("--prices", type=Path, required=True)
    args = parser.parse_args()
    report = daily_nav(args.database, args.previous_date, args.delivery, args.prices, args.business_date)
    folder = Path(__file__).resolve().parent / "data" / "daily_nav"
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{report['run_id']}.json"
    temporary = output.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2, default=str)
        file.write("\n")
    temporary.rename(output)
    close = report["close"]
    print(f"{report['business_date']} | {close['currency']} | {report['status']}")
    for field in ("cash", "receivables", "payables", "long_assets", "short_obligations", "nav"):
        print(f"{field}: {pounds(close[field])}")
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
