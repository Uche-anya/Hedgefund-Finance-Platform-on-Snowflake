"""Save an isolated OMS delivery with two conflicting reports."""

import argparse
from datetime import date
from pathlib import Path

from pipeline.load_day import delivery
from pipeline.sample_close import save
from pipeline.us_equity_calendar import is_market_day, next_settlement_day


def make_conflict(data_dir, business_date, scenario):
    day = date.fromisoformat(business_date)
    if not is_market_day(day):
        raise ValueError("Choose a reviewed US equity trading day")

    first = {
        "schema_version": 1,
        "event_id": "DRILL-EVENT-01",
        "event_type": "EXECUTION_REPORTED",
        "source_system": "simulated_oms",
        "scenario_id": scenario,
        "is_simulated": True,
        "occurred_at": business_date + "T19:55:00Z",
        "published_at": business_date + "T19:55:01Z",
        "executed_at": business_date + "T19:55:00Z",
        "business_date": business_date,
        "execution_id": "DRILL-EXEC-01",
        "execution_version": 1,
        "execution_status": "ACTIVE",
        "order_id": "DRILL-ORDER-01",
        "fund_id": "NORTHBRIDGE",
        "account_id": "SIM-ACCOUNT-01",
        "broker_id": "SIM-BROKER-01",
        "instrument_id": "AAPL.US",
        "market_ticker": "AAPL",
        "side": "BUY",
        "quantity": "10",
        "execution_price": "245.00",
        "currency": "USD",
        "settlement_due": next_settlement_day(day).isoformat(),
    }
    second = dict(first, event_id="DRILL-EVENT-02",
                  published_at=business_date + "T19:56:00Z", quantity="12")
    folder = data_dir / "daily_oms" / scenario / business_date
    save(folder, "oms.jsonl", [first, second], {
        "business_date": business_date,
        "scenario_id": scenario,
        "source_system": "simulated_oms",
        "is_simulated": True,
        "delivery_id": "oms-{}-{}".format(scenario, business_date),
    })
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", default="2026-10-09")
    parser.add_argument("--scenario", default="sim-oms-conflict-drill")
    parser.add_argument("--data-dir", type=Path, default=Path("data/drills"))
    args = parser.parse_args()
    try:
        folder = make_conflict(args.data_dir, args.business_date, args.scenario)
    except (OSError, ValueError) as error:
        parser.exit(1, "Drill stopped: {}\n".format(error))
    print("Saved isolated OMS drill in {}".format(folder))
    print("The two reports disagree on quantity without a version change.")
    try:
        delivery(args.data_dir, args.scenario, args.business_date, "oms")
    except ValueError as error:
        print("Delivery check rejected it: {}".format(error))
    else:
        parser.exit(1, "Drill failed: conflicting reports were accepted\n")


if __name__ == "__main__":
    main()
