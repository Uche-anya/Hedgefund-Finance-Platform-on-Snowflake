"""Deliver one PROD market day; Snowflake tasks build the close afterward."""

import argparse
import os
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

from pipeline import produce_bank, produce_day, produce_dividends
from pipeline.check_raw import check_source, readiness
from pipeline.environment import get_environment
from pipeline.load_day import snowflake_connection
from pipeline.us_equity_calendar import is_market_day


def run(business_date, scenario, opening_date, data_dir):
    if get_environment().name != "prod":
        raise ValueError("Daily PROD delivery requires NORTHBRIDGE_ENV=prod")
    if os.environ.get("SNOWFLAKE_ROLE") != "NORTHBRIDGE_INGEST_PROD":
        raise ValueError("Use the PROD loader role")

    day = date.fromisoformat(business_date)
    if not is_market_day(day):
        print("No US equity close on", business_date)
        return

    with snowflake_connection() as connection:
        with connection.cursor() as cursor:
            if produce_day.close_is_validated(cursor, business_date, scenario):
                print("Close already validated for", business_date)
                return

    produce_day.run(business_date, scenario, data_dir, True)
    produce_dividends.run(business_date, data_dir, True)

    # The two event files are asynchronous. Bank cash uses the executed trades.
    for attempt in range(40):
        with snowflake_connection() as connection:
            with connection.cursor() as cursor:
                oms, _ = check_source(cursor, business_date, scenario, "oms")
                settlements, _ = check_source(cursor, business_date, scenario, "settlements")
        if oms and settlements:
            break
        if attempt == 39:
            raise RuntimeError("Snowpipe did not finish the event deliveries")
        time.sleep(15)

    produce_bank.run(business_date, opening_date, scenario, data_dir, True)
    with snowflake_connection() as connection:
        with connection.cursor() as cursor:
            checks = readiness(cursor, business_date, scenario, opening_date)
    for passed, message in checks:
        print(message)
    if not all(passed for passed, _ in checks):
        raise RuntimeError("Daily deliveries are incomplete")
    print("RAW ready for", business_date, "- waiting for Snowflake close tasks")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", help="US market date; default is yesterday in UTC")
    parser.add_argument("--scenario", default="sim-prod-20261016")
    parser.add_argument("--opening-date", default="2026-10-15")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    business_date = args.business_date or (
        datetime.now(timezone.utc).date() - timedelta(days=1)
    ).isoformat()
    run(business_date, args.scenario, args.opening_date, args.data_dir)


if __name__ == "__main__":
    main()
