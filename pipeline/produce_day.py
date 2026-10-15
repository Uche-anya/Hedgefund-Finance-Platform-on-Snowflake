"""Fetch the market close, save fictional activity, and submit the deliveries."""

import argparse
from datetime import date
from pathlib import Path

from pipeline import daily_simulator, load_day, massive_prices, prices
from pipeline.check_day import closing_prices
from pipeline.us_equity_calendar import is_market_day


def close_is_validated(cursor, business_date, scenario):
    cursor.execute(
        "SELECT COUNT(*) FROM NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS "
        "WHERE business_date = %s AND scenario_id = %s AND status = 'VALIDATED'",
        (business_date, scenario)
    )
    return cursor.fetchone()[0] == 1


def save_market_evidence(cursor, price_file, delivery_id):
    folder = price_file.parent
    target = ("@NORTHBRIDGE_DEV.RAW.DAILY_LANDING/provider_evidence/"
              "delivery_id={}/".format(delivery_id))
    for name in ("prices.csv", "response.json", "manifest.json"):
        path = folder / name
        if not path.is_file():
            raise ValueError("Missing Massive evidence: {}".format(path))
        staged = target + name
        if load_day.stage_has_file(cursor, staged, staged.split("DAILY_LANDING/", 1)[1]):
            continue
        uri = "file://" + path.resolve().as_posix()
        cursor.execute("PUT '{}' '{}' AUTO_COMPRESS = FALSE OVERWRITE = FALSE".format(
            uri.replace("'", "''"), target))


def run(business_date, scenario, data_dir, submit):
    day = date.fromisoformat(business_date)
    if not is_market_day(day):
        raise ValueError("No scheduled US equity close on this date")

    if submit:
        with load_day.snowflake_connection() as connection:
            with connection.cursor() as cursor:
                if close_is_validated(cursor, business_date, scenario):
                    print("Close already validated for {}; no new delivery".format(
                        business_date))
                    return

    price_file = massive_prices.fetch(business_date, data_dir)
    with load_day.snowflake_connection() as connection:
        with connection.cursor() as cursor:
            previous = daily_simulator.prior_close(cursor, business_date, scenario)
            closes = daily_simulator.prior_prices(cursor, previous, business_date)
            due = daily_simulator.unsettled_trades(cursor, business_date, scenario)
            trades, settlements = daily_simulator.write_day(
                business_date, scenario, data_dir, previous, closes, due)
            sources = [load_day.delivery(data_dir, scenario, business_date, source)
                       for source in ("oms", "settlements")]
            held = {row["market_ticker"] for row in sources[0]["records"]}
            if closing_prices(price_file, business_date, held) != held:
                raise ValueError("Massive close is missing a traded stock")
            market = prices.prepare(price_file, data_dir, business_date)
            print("{}: {} fictional trades, {} fictional settlements, {} real closes".format(
                business_date, trades, settlements, market["rows"]))
            if not submit:
                print("Saved files only; add --submit to load Snowflake")
                return
            for source in sources:
                load_day.submit(cursor, source)
            prices.submit(cursor, market)
            save_market_evidence(cursor, price_file, market["id"])
            print("Files submitted. Snowflake will check RAW before dbt runs.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date", help="US market date, YYYY-MM-DD")
    parser.add_argument("--scenario", default="sim-close-20261008")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    try:
        run(args.business_date, args.scenario, args.data_dir, args.submit)
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, "Daily producer stopped: {}\n".format(error))


if __name__ == "__main__":
    main()
