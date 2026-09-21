"""Connect preserved real USD prices to explicitly simulated fund activity."""

import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from landing import land_delivery
from market_prices import DATES, verify_market


def write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)


def build_hybrid(market_folder, root):
    rows = verify_market(market_folder)
    prices = {(row["valuation_date"], row["instrument"]): Decimal(row["close_price"]) for row in rows}
    first, settlement_date, last = DATES
    apple_entry = prices[(first, "AAPL.US")]
    amazon_entry = prices[(first, "AMZN.US")]
    buy_amount = apple_entry * 10
    short_proceeds = amazon_entry * 5
    for amount in (buy_amount, short_proceeds):
        if amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Hypothetical executions must settle in whole cents")

    folder = root / "hybrid" / uuid4().hex
    source, reference = folder / "activity", folder / "references"
    source.mkdir(parents=True)
    reference.mkdir()
    write_csv(source / "executions.csv", ["business_date", "execution_id", "instrument", "side", "quantity"], [
        [first, "SIM-E001", "AAPL.US", "BUY", 10], [first, "SIM-E002", "AMZN.US", "SELL", 5]])
    write_csv(source / "allocations.csv", ["business_date", "allocation_id", "execution_id", "portfolio", "quantity"], [
        [first, "SIM-A001", "SIM-E001", "GROWTH", 10], [first, "SIM-A002", "SIM-E002", "HEDGE", 5]])
    write_csv(source / "execution_terms.csv", ["business_date", "execution_id", "currency", "execution_price", "settlement_due"], [
        [first, "SIM-E001", "USD", apple_entry, settlement_date], [first, "SIM-E002", "USD", amazon_entry, settlement_date]])
    write_csv(source / "opening_cash.csv", ["business_date", "currency", "balance"], [[first, "USD", "10000.00"]])
    write_csv(source / "settlements.csv", ["business_date", "settlement_id", "execution_id", "currency", "amount", "settled_on"], [
        [first, "SIM-S001", "SIM-E001", "USD", buy_amount, settlement_date],
        [first, "SIM-S002", "SIM-E002", "USD", short_proceeds, settlement_date]])
    (source / "closing_prices.csv").write_bytes((market_folder / "closing_prices.csv").read_bytes())

    # Separate scenario-specific reference arithmetic; never call calculate_nav().
    reference_cash = Decimal("10000") - 10 * apple_entry + 5 * amazon_entry
    reference_nav = (Decimal("10000") + 10 * (prices[(last, "AAPL.US")] - apple_entry)
                     + 5 * (amazon_entry - prices[(last, "AMZN.US")]))
    write_csv(reference / "broker_positions.csv", ["business_date", "fund", "portfolio", "instrument", "basis", "quantity"], [
        [last, "NORTHBRIDGE", "GROWTH", "AAPL.US", "TRADE_DATE", 10],
        [last, "NORTHBRIDGE", "HEDGE", "AMZN.US", "TRADE_DATE", -5]])
    write_csv(reference / "broker_cash.csv", ["business_date", "fund", "currency", "basis", "balance"], [
        [last, "NORTHBRIDGE", "USD", "SETTLED", reference_cash]])
    write_csv(reference / "administrator_nav.csv", ["business_date", "fund", "currency", "nav"], [
        [last, "NORTHBRIDGE", "USD", reference_nav]])
    provenance = {
        "market_delivery": str(market_folder.resolve()),
        "market_manifest_sha256": hashlib.sha256((market_folder / "manifest.json").read_bytes()).hexdigest(),
        "real_inputs": "EODHD historical closes for AAPL.US and AMZN.US",
        "simulated_inputs": "All executions, allocations, opening cash and settlement confirmations",
        "reference_method": "Separate scenario arithmetic from initial capital plus long/short price changes; not external validation",
        "currency": "USD", "fx_conversion": False,
        "usage": "Private learning only; do not redistribute prices or derived examples",
    }
    nav_delivery = land_delivery(source, root / "landing", first, "nav",
                                 "hybrid_eodhd_and_simulated_activity", provenance)
    reference_delivery = land_delivery(reference, root / "landing", last, "references",
                                       "simulated_comparison_statements", provenance)
    result = {"nav_delivery": str(nav_delivery.resolve()), "reference_delivery": str(reference_delivery.resolve()),
              "trade_date": first, "as_of": last, "currency": "USD", "provenance": provenance}
    (folder / "scenario.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market-delivery", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_hybrid(args.market_delivery, Path(__file__).resolve().parent / "data"), indent=2))
