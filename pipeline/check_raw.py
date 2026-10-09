"""Stop a daily run until events and real closing prices are in RAW."""

import argparse
from datetime import date

from pipeline.load_day import REGISTRY, snowflake_connection
from pipeline.prices import MARKET, TABLE as PRICE_TABLE


RAW_TABLE = {
    "oms": "NORTHBRIDGE_DEV.RAW.DAILY_OMS_EVENTS",
    "settlements": "NORTHBRIDGE_DEV.RAW.DAILY_SETTLEMENT_EVENTS",
    "prices": PRICE_TABLE,
    "opening_bank": "NORTHBRIDGE_DEV.RAW.DAILY_OPENING_EVENTS",
    "opening_admin": "NORTHBRIDGE_DEV.RAW.DAILY_OPENING_EVENTS",
}


def check_source(cursor, business_date, scenario, source):
    cursor.execute(
        "SELECT delivery_id, expected_rows, stage_path, status FROM " + REGISTRY +
        " WHERE business_date = %s AND scenario_id = %s AND source_name = %s",
        (business_date, scenario, source)
    )
    deliveries = cursor.fetchall()
    if len(deliveries) != 1:
        return False, "{}: expected one delivery, found {}".format(source, len(deliveries))

    delivery_id, expected_rows, stage_path, status = deliveries[0]
    cursor.execute(
        "SELECT COUNT(*) FROM " + RAW_TABLE[source] +
        " WHERE ENDSWITH(source_file, %s)",
        (stage_path,)
    )
    loaded_rows = cursor.fetchone()[0]
    if expected_rows == 0 and status == "EMPTY" and loaded_rows == 0:
        return True, "{}: ready, empty delivery {}".format(source, delivery_id)
    if expected_rows > 0 and status in ("SUBMITTED", "LOADED") and loaded_rows == expected_rows:
        return True, "{}: ready, {} rows ({})".format(source, loaded_rows, delivery_id)
    return False, "{}: waiting, {} of {} rows loaded ({})".format(
        source, loaded_rows, expected_rows, delivery_id
    )


def check_held_prices(cursor, business_date, scenario):
    cursor.execute(
        "SELECT stage_path FROM " + REGISTRY + " WHERE source_name = 'prices' "
        "AND business_date = %s AND scenario_id = %s AND status = 'LOADED'",
        (business_date, MARKET)
    )
    saved = cursor.fetchall()
    if len(saved) != 1:
        return False, "prices: no single loaded market delivery"
    path = saved[0][0]

    cursor.execute(
        "SELECT COUNT(*), COUNT(DISTINCT payload:universe_ticker::varchar), "
        "COUNT_IF(TRY_TO_DATE(payload:valuation_date::varchar) IS NULL "
        "OR TRY_TO_DATE(payload:valuation_date::varchar) <> TO_DATE(%s) "
        "OR payload:universe_ticker::varchar IS NULL "
        "OR payload:currency::varchar IS NULL "
        "OR payload:currency::varchar <> 'USD' "
        "OR payload:price_basis::varchar IS NULL "
        "OR payload:price_basis::varchar <> 'unadjusted' "
        "OR TRY_TO_DECIMAL(payload:close_price::varchar, 38, 9) <= 0 "
        "OR TRY_TO_DECIMAL(payload:close_price::varchar, 38, 9) IS NULL) "
        "FROM " + PRICE_TABLE + " WHERE ENDSWITH(source_file, %s)",
        (business_date, path)
    )
    total, tickers, invalid = cursor.fetchone()
    if total != tickers or invalid:
        return False, "prices: duplicate tickers or invalid close rows"

    cursor.execute(
        "WITH positions AS ("
        " SELECT payload:account_id::varchar AS account_id, "
        " payload:instrument_id::varchar AS instrument_id, "
        " payload:market_ticker::varchar AS ticker, "
        " SUM(CASE payload:side::varchar WHEN 'BUY' THEN "
        " TRY_TO_DECIMAL(payload:quantity::varchar, 38, 9) "
        " WHEN 'SELL' THEN -TRY_TO_DECIMAL(payload:quantity::varchar, 38, 9) END) AS shares "
        " FROM NORTHBRIDGE_DEV.RAW.DAILY_OMS_EVENTS "
        " WHERE payload:scenario_id::varchar = %s "
        " AND TRY_TO_DATE(payload:business_date::varchar) <= TO_DATE(%s) "
        " GROUP BY 1, 2, 3 HAVING shares <> 0"
        "), priced AS ("
        " SELECT payload:universe_ticker::varchar AS ticker "
        " FROM " + PRICE_TABLE + " WHERE ENDSWITH(source_file, %s)"
        ") SELECT DISTINCT p.ticker FROM positions p "
        " LEFT JOIN priced q ON p.ticker = q.ticker "
        " WHERE q.ticker IS NULL OR p.ticker IS NULL ORDER BY p.ticker",
        (scenario, business_date, path)
    )
    missing = [row[0] for row in cursor.fetchall()]
    if missing:
        return False, "prices: missing for held stocks {}".format(", ".join(str(x) for x in missing))
    return True, "prices: all held stocks have a close"


def readiness(cursor, business_date, scenario, opening_date):
    results = [check_source(cursor, business_date, scenario, source)
               for source in ("oms", "settlements")]
    results += [check_source(cursor, opening_date, scenario, source)
                for source in ("opening_bank", "opening_admin")]
    price_ready, price_message = check_source(cursor, business_date, MARKET, "prices")
    results.append((price_ready, price_message))
    if price_ready:
        results.append(check_held_prices(cursor, business_date, scenario))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date", help="YYYY-MM-DD")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--opening-date", required=True)
    args = parser.parse_args()
    try:
        date.fromisoformat(args.business_date)
        date.fromisoformat(args.opening_date)
        if args.opening_date >= args.business_date:
            raise ValueError("Opening date must precede the close date")
    except ValueError:
        parser.exit(2, "Business date must be YYYY-MM-DD.\n")

    try:
        with snowflake_connection() as connection:
            with connection.cursor() as cursor:
                results = readiness(cursor, args.business_date, args.scenario,
                                    args.opening_date)
    except (ValueError, ModuleNotFoundError) as error:
        parser.exit(1, "Cannot check RAW: {}\n".format(error))

    for ready, message in results:
        print(message)
    if not all(ready for ready, message in results):
        parser.exit(1, "RAW is not ready for the close.\n")


if __name__ == "__main__":
    main()
