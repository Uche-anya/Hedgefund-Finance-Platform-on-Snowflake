"""Check that the latest dividend delivery reached RAW for a market day."""

import argparse
from datetime import date, datetime, timezone

from pipeline.load_day import snowflake_connection
from pipeline.environment import get_environment
from pipeline.schedule_day import scheduled_close
from pipeline.us_equity_calendar import is_market_day


DELIVERIES = get_environment().raw("DAILY_DELIVERIES")
EVENTS = get_environment().raw("DAILY_DIVIDEND_EVENTS")


def dividend_readiness(cursor, business_date):
    cursor.execute(
        "SELECT d.delivery_id, d.expected_rows, d.status, COUNT(r.source_file) "
        "FROM " + DELIVERIES + " d LEFT JOIN " + EVENTS + " r "
        "ON ENDSWITH(r.source_file, d.stage_path) "
        "WHERE d.source_name = 'dividends' AND d.scenario_id = 'massive' "
        "AND d.business_date = %s "
        "GROUP BY d.delivery_id, d.expected_rows, d.status, d.stage_path, d.registered_at "
        "ORDER BY d.registered_at DESC, d.delivery_id DESC",
        (business_date,)
    )
    rows = cursor.fetchall()
    if not rows:
        return False, "No dividend delivery for {}".format(business_date)
    delivery_id, expected, status, loaded = rows[0]
    if not (status == "LOADED" and expected > 0 and loaded == expected):
        return False, "Latest dividend delivery {} is {}: expected {}, found {}".format(
            delivery_id, status, expected, loaded)
    return True, "Dividend delivery checked for {}: {} rows ({})".format(
        business_date, loaded, delivery_id)


def check_dividends(cursor, business_date):
    ready, message = dividend_readiness(cursor, business_date)
    if not ready:
        raise RuntimeError(message)
    print(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-date", help="Check a specific US market date")
    args = parser.parse_args()
    try:
        day = (date.fromisoformat(args.business_date) if args.business_date
               else scheduled_close(datetime.now(timezone.utc)))
        if day is None or not is_market_day(day):
            print("No US equity close due for this date")
            return
        with snowflake_connection() as connection:
            with connection.cursor() as cursor:
                check_dividends(cursor, day.isoformat())
    except (ValueError, RuntimeError, ModuleNotFoundError) as error:
        parser.exit(1, "Dividend deadline check failed: {}\n".format(error))


if __name__ == "__main__":
    main()
