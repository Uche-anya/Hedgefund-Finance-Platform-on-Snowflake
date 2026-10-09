"""Load a saved day, wait for Snowpipe, and validate its dbt close."""

import argparse
import json
import os
import subprocess
import time
import uuid
from datetime import date
from pathlib import Path

from pipeline import load_day, massive_prices, opening, prices
from pipeline.check_day import closing_prices, read_delivery
from pipeline.check_raw import readiness


RUNS = "NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS"
NAV = "NORTHBRIDGE_DEV.DBT_DEV.FCT_NAV_DAILY"


def prepare(data_dir, price_csv, business_date, opening_date, scenario):
    opened = [opening.delivery(data_dir, scenario, opening_date, source)
              for source in ("opening_bank", "opening_admin")]
    events = [load_day.delivery(data_dir, scenario, business_date, source)
              for source in ("oms", "settlements")]
    tickers = {record["market_ticker"] for record in events[0]["records"]}
    if closing_prices(price_csv, business_date, tickers) != tickers:
        raise ValueError("Saved prices do not cover today's trades")
    market = prices.prepare(price_csv, data_dir, business_date)
    return opened, events, market


def start_run(cursor, run_id, business_date, scenario, opening_date):
    cursor.execute(
        "INSERT INTO " + RUNS + " (run_id, business_date, scenario_id, opening_date, "
        "status) VALUES (%s, %s, %s, %s, 'RUNNING')",
        (run_id, business_date, scenario, opening_date)
    )


def finish_run(cursor, run_id, status, detail):
    cursor.execute(
        "UPDATE " + RUNS + " SET status = %s, detail = %s, "
        "finished_at = CURRENT_TIMESTAMP() WHERE run_id = %s",
        (status, detail[:1000], run_id)
    )


def wait_for_raw(cursor, business_date, scenario, opening_date, timeout):
    deadline = time.monotonic() + timeout
    while True:
        results = readiness(cursor, business_date, scenario, opening_date)
        if all(ready for ready, _ in results):
            for _, message in results:
                print(message)
            return
        if time.monotonic() >= deadline:
            waiting = [message for ready, message in results if not ready]
            raise TimeoutError("; ".join(waiting))
        print("Waiting for Snowpipe...", flush=True)
        time.sleep(5)


def build_dbt(project_dir, business_date, opening_date, scenario, run_id, data_dir):
    if not os.environ.get("NORTHBRIDGE_DBT_KEY_PATH"):
        raise ValueError("NORTHBRIDGE_DBT_KEY_PATH is not set")
    dbt = project_dir.parent / ".venv" / "dbt" / "Scripts" / "dbt.exe"
    if not dbt.is_file():
        raise ValueError("dbt executable is missing: {}".format(dbt))
    variables = json.dumps({"business_date": business_date,
                            "opening_date": opening_date,
                            "scenario_id": scenario})
    command = [str(dbt), "build", "--project-dir", str(project_dir),
               "--profiles-dir", str(project_dir), "--vars", variables]
    result = subprocess.run(command, cwd=project_dir.parent,
                            capture_output=True, text=True)
    log_dir = data_dir / "close_runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / (run_id + ".log")).write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    print("\n".join(result.stdout.splitlines()[-7:]))
    if result.returncode:
        raise RuntimeError("dbt build failed; see data/close_runs/{}.log".format(run_id))


def check_nav(business_date, scenario, expected_accounts):
    import snowflake.connector

    with snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user="NORTHBRIDGE_DBT",
        authenticator="SNOWFLAKE_JWT",
        private_key_file=os.environ["NORTHBRIDGE_DBT_KEY_PATH"],
        role="NORTHBRIDGE_DBT_DEV",
        warehouse="COMPUTE_WH",
        database="NORTHBRIDGE_DEV",
        schema="DBT_DEV",
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT account_id, nav_usd FROM " + NAV +
                " WHERE valuation_date = %s AND scenario_id = %s",
                (business_date, scenario)
            )
            rows = cursor.fetchall()
    accounts = {account for account, nav in rows if nav is not None}
    if len(rows) != len(expected_accounts) or accounts != expected_accounts:
        raise RuntimeError("NAV rows do not match the opening accounts")
    for account, nav in sorted(rows):
        print("{}: NAV USD {}".format(account, nav))


def run(args):
    business_date = date.fromisoformat(args.business_date).isoformat()
    opening_date = date.fromisoformat(args.opening_date).isoformat()
    if opening_date >= business_date:
        raise ValueError("Opening date must precede the close date")
    run_id = uuid.uuid4().hex
    project_dir = Path("dbt").resolve()
    if not args.submit:
        price_file = (massive_prices.fetch(business_date, args.data_dir)
                      if args.fetch_prices else args.prices)
        opened, events, market = prepare(args.data_dir, price_file, business_date,
                                         opening_date, args.scenario)
        print("Prepared {} OMS, {} settlements and {} prices for {}".format(
            events[0]["rows"], events[1]["rows"], market["rows"], business_date))
        print("Local check only. Add --submit to run the Snowflake close.")
        return
    if not os.environ.get("NORTHBRIDGE_DBT_KEY_PATH"):
        raise ValueError("NORTHBRIDGE_DBT_KEY_PATH is not set")

    with load_day.snowflake_connection() as connection:
        with connection.cursor() as cursor:
            start_run(cursor, run_id, business_date, args.scenario, opening_date)
            try:
                price_file = (massive_prices.fetch(business_date, args.data_dir)
                              if args.fetch_prices else args.prices)
                opened, events, market = prepare(args.data_dir, price_file,
                                                 business_date, opening_date,
                                                 args.scenario)
                print("Prepared {} OMS, {} settlements and {} prices for {}".format(
                    events[0]["rows"], events[1]["rows"], market["rows"],
                    business_date))
                for item in opened:
                    opening.submit(cursor, item)
                for item in events:
                    load_day.submit(cursor, item)
                prices.submit(cursor, market)
                wait_for_raw(cursor, business_date, args.scenario,
                             opening_date, args.timeout)
                build_dbt(project_dir, business_date, opening_date, args.scenario,
                          run_id, args.data_dir)
                expected = {row["account_id"] for row in
                            read_delivery(
                                args.data_dir / "daily_opening" / args.scenario /
                                opening_date / "bank_cash", "balances.jsonl",
                                "business_date", opening_date, args.scenario,
                                "statement_date")[1]}
                check_nav(business_date, args.scenario, expected)
            except TimeoutError as error:
                finish_run(cursor, run_id, "WAITING_INPUTS", str(error))
                raise
            except Exception as error:
                finish_run(cursor, run_id, "FAILED", str(error))
                raise
            finish_run(cursor, run_id, "VALIDATED", "dbt passed; NAV accounts checked")
    print("Validated close for {}. Run ID: {}".format(business_date, run_id))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--opening-date", required=True)
    market = parser.add_mutually_exclusive_group(required=True)
    market.add_argument("--prices", type=Path, help="Use an existing price CSV")
    market.add_argument("--fetch-prices", action="store_true",
                        help="Fetch an immutable daily delivery from Massive")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--timeout", type=int, default=120,
                        help="Seconds to wait for Snowpipe")
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, OSError, RuntimeError, TimeoutError, ModuleNotFoundError) as error:
        parser.exit(1, "Close stopped: {}\n".format(error))


if __name__ == "__main__":
    main()
