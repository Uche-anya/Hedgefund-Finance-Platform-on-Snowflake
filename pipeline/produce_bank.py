"""Produce the fictional bank's daily cash ledger."""

import argparse
import csv
import json
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from pipeline import bank_statements
from pipeline.check_raw import check_source
from pipeline.load_day import snowflake_connection
from pipeline.environment import get_environment
from pipeline.us_equity_calendar import is_market_day, previous_market_day


ENV = get_environment()
OPENING = ENV.raw("DAILY_OPENING_EVENTS")
DELIVERIES = ENV.raw("DAILY_DELIVERIES")
TRADES = ENV.raw("DAILY_OMS_EVENTS")
STATEMENTS = ENV.raw("DAILY_BANK_STATEMENTS")
EXPOSURE = ENV.dbt("FCT_DIVIDEND_EXPOSURE")
CLOSE_RUNS = ENV.raw("DAILY_CLOSE_RUNS")


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
        raise ValueError("Bank amount must be finite and have two decimal places")
    return amount


def ledger(cursor, business_date, opening_date, scenario):
    ready, message = check_source(cursor, business_date, scenario, "oms")
    if not ready:
        raise ValueError(message)
    cursor.execute(
        "SELECT MAX(business_date) FROM " + DELIVERIES + " WHERE source_name = 'bank' "
        "AND scenario_id = %s AND status = 'LOADED' AND business_date < TO_DATE(%s)",
        (scenario, business_date)
    )
    previous = cursor.fetchone()[0]
    if previous and str(previous) != previous_market_day(date.fromisoformat(business_date)).isoformat():
        raise ValueError("Previous market day's bank statement is missing")
    if previous:
        cursor.execute(
            "SELECT COUNT(*) FROM " + CLOSE_RUNS + " WHERE scenario_id = %s "
            "AND business_date = TO_DATE(%s) AND status = 'VALIDATED'",
            (scenario, str(previous))
        )
        if cursor.fetchone()[0] != 1:
            raise ValueError("Previous bank day has no single validated close")
    start = str(previous) if previous else opening_date
    if previous:
        cursor.execute(
            "SELECT r.payload:account_id::varchar, r.payload:currency::varchar, "
            "r.payload:closing_balance::varchar FROM " + STATEMENTS + " r "
            "JOIN " + DELIVERIES + " d ON d.source_name = 'bank' "
            "AND d.scenario_id = %s AND d.business_date = TO_DATE(%s) "
            "AND d.status = 'LOADED' AND ENDSWITH(r.source_file, d.stage_path)",
            (scenario, start)
        )
    else:
        ready, message = check_source(cursor, opening_date, scenario, "opening_bank")
        if not ready:
            raise ValueError(message)
        cursor.execute(
            "SELECT r.payload:account_id::varchar, r.payload:currency::varchar, "
            "r.payload:closing_balance::varchar FROM " + OPENING + " r "
            "JOIN " + DELIVERIES + " d ON d.source_name = 'opening_bank' "
            "AND d.scenario_id = %s AND d.business_date = TO_DATE(%s) "
            "AND d.status = 'LOADED' AND ENDSWITH(r.source_file, d.stage_path)",
            (scenario, start)
        )
    accounts = {}
    for account, currency, amount in cursor.fetchall():
        if not account or account in accounts or currency != "USD":
            raise ValueError("Bad bank account or currency")
        accounts[account] = {"opening_balance": money(amount), "postings": []}
    if len(accounts) != 2:
        raise ValueError("Expected two bank accounts")

    cursor.execute(
        "SELECT COUNT(*) FROM " + EXPOSURE + " WHERE scenario_id = %s "
        "AND pay_date > TO_DATE(%s) AND pay_date <= TO_DATE(%s) "
        "AND expected_cash_usd <> 0", (scenario, start, business_date)
    )
    if cursor.fetchone()[0]:
        raise ValueError("Dividend payment evidence is needed for the bank ledger")

    cursor.execute(
        "SELECT r.payload:execution_id::varchar, r.payload:account_id::varchar, "
        "r.payload:side::varchar, r.payload:quantity::varchar, "
        "r.payload:execution_price::varchar, r.payload:currency::varchar, "
        "r.payload:settlement_due::varchar FROM " + TRADES + " r "
        "JOIN " + DELIVERIES + " d ON d.source_name = 'oms' "
        "AND d.scenario_id = %s AND d.status = 'SUBMITTED' "
        "AND d.business_date > TO_DATE(%s) AND d.business_date <= TO_DATE(%s) "
        "AND ENDSWITH(r.source_file, d.stage_path) "
        "WHERE r.payload:execution_status::varchar = 'ACTIVE' "
        "AND TRY_TO_DATE(r.payload:settlement_due::varchar) > TO_DATE(%s) "
        "AND TRY_TO_DATE(r.payload:settlement_due::varchar) <= TO_DATE(%s)",
        (scenario, opening_date, business_date, start, business_date)
    )
    seen = set()
    for execution_id, account, side, quantity, price, currency, due in cursor.fetchall():
        if not execution_id or execution_id in seen or account not in accounts or currency != "USD":
            raise ValueError("Repeated or invalid bank posting")
        if side not in ("BUY", "SELL"):
            raise ValueError("Bad trade side in bank posting")
        shares = Decimal(str(quantity))
        trade_price = Decimal(str(price))
        if not shares.is_finite() or not trade_price.is_finite() or shares <= 0 or trade_price <= 0:
            raise ValueError("Bad trade quantity or price in bank posting")
        amount = money(shares * trade_price)
        accounts[account]["postings"].append({
            "posting_id": "SETTLEMENT-" + execution_id,
            "posting_date": str(due),
            "amount": format(-amount if side == "BUY" else amount, ".2f"),
            "type": "TRADE_SETTLEMENT",
        })
        seen.add(execution_id)
    for value in accounts.values():
        value["postings"].sort(key=lambda row: row["posting_id"])
        value["closing_balance"] = value["opening_balance"] + sum(
            (Decimal(row["amount"]) for row in value["postings"]), Decimal("0")
        )
    return start, accounts


def write_statement(data_dir, business_date, scenario, accounts):
    path = data_dir / "bank_inputs" / scenario / business_date / "statement.csv"
    rows = ["account_id,currency,opening_balance,closing_balance,postings_json\n"]
    for account in sorted(accounts):
        value = accounts[account]
        buffer = StringIO()
        csv.writer(buffer, lineterminator="\n").writerow((
            account, "USD", format(value["opening_balance"], ".2f"),
            format(value["closing_balance"], ".2f"),
            json.dumps(value["postings"], sort_keys=True, separators=(",", ":"))
        ))
        rows.append(buffer.getvalue())
    content = "".join(rows)
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("Saved bank input changed: {}".format(path))
    else:
        path.parent.mkdir(parents=True)
        path.write_text(content, encoding="utf-8")
    return path


def run(business_date, opening_date, scenario, data_dir, submit):
    day = date.fromisoformat(business_date)
    if not is_market_day(day) or date.fromisoformat(opening_date) >= day:
        raise ValueError("Expected a market day after the opening date")
    with snowflake_connection() as connection:
        with connection.cursor() as cursor:
            start, accounts = ledger(cursor, business_date, opening_date, scenario)
            statement = write_statement(data_dir, business_date, scenario, accounts)
            item = bank_statements.prepare(statement, data_dir, business_date, scenario,
                                           previous_date=start)
            print("Prepared {} bank ledgers for {}".format(item["rows"], business_date))
            if submit:
                bank_statements.submit(cursor, item)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--opening-date", default="2026-10-07")
    parser.add_argument("--scenario", default="sim-close-20261008")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--submit", action="store_true")
    args = parser.parse_args()
    try:
        run(args.business_date, args.opening_date, args.scenario, args.data_dir, args.submit)
    except (OSError, ValueError) as error:
        parser.exit(1, "Bank producer stopped: {}\n".format(error))


if __name__ == "__main__":
    main()
