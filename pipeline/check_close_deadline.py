"""Fail the overnight check if yesterday's market close was not validated."""

import argparse
from datetime import date, datetime, timezone

from pipeline.load_day import snowflake_connection
from pipeline.environment import get_environment
from pipeline.schedule_day import scheduled_close
from pipeline.us_equity_calendar import is_market_day


RUNS = get_environment().raw("DAILY_CLOSE_RUNS")


def check_close(cursor, business_date, scenario):
    cursor.execute(
        "SELECT status FROM " + RUNS +
        " WHERE business_date = %s AND scenario_id = %s",
        (business_date, scenario)
    )
    statuses = [row[0] for row in cursor.fetchall()]
    if statuses.count("VALIDATED") != 1:
        raise RuntimeError("No single validated close for {}: {}".format(
            business_date, ", ".join(statuses) or "no run recorded"))
    print("Validated close found for {}".format(business_date))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", help="Check a specific US market date")
    parser.add_argument("--scenario", default="sim-close-20261008")
    args = parser.parse_args()

    try:
        if args.business_date:
            day = date.fromisoformat(args.business_date)
        else:
            day = scheduled_close(datetime.now(timezone.utc))
        if day is None or not is_market_day(day):
            print("No US equity close due for this date")
            return
        with snowflake_connection() as connection:
            with connection.cursor() as cursor:
                check_close(cursor, day.isoformat(), args.scenario)
    except (ValueError, RuntimeError, ModuleNotFoundError) as error:
        parser.exit(1, "Close deadline check failed: {}\n".format(error))


if __name__ == "__main__":
    main()
