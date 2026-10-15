"""Fetch a dated dividend snapshot and submit it to Snowflake."""

import argparse
from datetime import date
from pathlib import Path

from pipeline import dividends, massive_dividends
from pipeline.load_day import REGISTRY, snowflake_connection
from pipeline.us_equity_calendar import is_market_day


def dividend_is_loaded(cursor, business_date):
    cursor.execute(
        "SELECT status FROM " + REGISTRY +
        " WHERE source_name = 'dividends' AND scenario_id = 'massive' "
        "AND business_date = %s", (business_date,)
    )
    statuses = [row[0] for row in cursor.fetchall()]
    if len(statuses) > 1:
        raise ValueError("More than one dividend delivery for {}".format(business_date))
    return statuses == ["LOADED"]


def run(business_date, data_dir, submit):
    day = date.fromisoformat(business_date)
    if not is_market_day(day):
        raise ValueError("No US equity close on this date")

    if submit:
        with snowflake_connection() as connection:
            with connection.cursor() as cursor:
                if dividend_is_loaded(cursor, business_date):
                    print("Dividends already loaded for {}; no new delivery".format(
                        business_date))
                    return

    folder = massive_dividends.fetch(business_date, data_dir)
    item = dividends.prepare(folder)
    if item["rows"] == 0:
        raise RuntimeError("Massive returned no dividends in the full date window")
    print("{}: {} dividend events saved".format(business_date, item["rows"]))
    if not submit:
        print("Saved files only; add --submit to load Snowflake")
        return folder

    with snowflake_connection() as connection:
        with connection.cursor() as cursor:
            dividends.submit(cursor, item)
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date", help="US market date, YYYY-MM-DD")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    try:
        run(args.business_date, args.data_dir, args.submit)
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        parser.exit(1, "Dividend producer stopped: {}\n".format(error))


if __name__ == "__main__":
    main()
