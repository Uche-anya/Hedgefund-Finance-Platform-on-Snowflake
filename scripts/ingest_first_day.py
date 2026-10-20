"""Load a first fund day from saved provider and fictional source files."""

import argparse
import os
from pathlib import Path

from pipeline import dividends, load_day, opening, prices, sample_close
from pipeline.environment import get_environment


def run(business_date, opening_date, settlement_due, scenario, dividend_folder, data_dir):
    env = get_environment()
    if env.name not in ("test", "prod"):
        raise ValueError("Choose TEST or PROD explicitly")
    if os.environ.get("SNOWFLAKE_ROLE") != "NORTHBRIDGE_INGEST_" + env.name.upper():
        raise ValueError("Use the {} loader role".format(env.name.upper()))

    reference = data_dir / "provider_prices" / "massive" / opening_date / "prices.csv"
    close = data_dir / "provider_prices" / "massive" / business_date / "prices.csv"
    sample_close.make_day(business_date, opening_date, settlement_due,
                          scenario, reference, data_dir)

    opening_files = [opening.delivery(data_dir, scenario, opening_date, source)
                     for source in ("opening_bank", "opening_admin")]
    market_files = [prices.prepare(reference, data_dir, opening_date),
                    prices.prepare(close, data_dir, business_date)]
    activity_files = [load_day.delivery(data_dir, scenario, business_date, source)
                      for source in ("oms", "settlements")]
    dividend_file = dividends.prepare(dividend_folder)
    if dividend_file["date"] != business_date:
        raise ValueError("Dividend snapshot belongs to another date")

    with load_day.snowflake_connection() as connection:
        with connection.cursor() as cursor:
            for item in opening_files:
                opening.submit(cursor, item)
            for item in market_files:
                prices.submit(cursor, item)
            for item in activity_files:
                load_day.submit(cursor, item)
            dividends.submit(cursor, dividend_file)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--opening-date", required=True)
    parser.add_argument("--settlement-due", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--dividend-folder", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    run(args.business_date, args.opening_date, args.settlement_due,
        args.scenario, args.dividend_folder, args.data_dir)


if __name__ == "__main__":
    main()
