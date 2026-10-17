"""Make a simulated bank statement from opening cash and due trades."""

import argparse
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from pipeline import bank_statements
from pipeline.check_raw import check_source
from pipeline.load_day import snowflake_connection
from pipeline.us_equity_calendar import is_market_day


OPENING = "NORTHBRIDGE_DEV.RAW.DAILY_OPENING_EVENTS"
DELIVERIES = "NORTHBRIDGE_DEV.RAW.DAILY_DELIVERIES"
TRADES = "NORTHBRIDGE_DEV.RAW.DAILY_OMS_EVENTS"
EXPOSURE = "NORTHBRIDGE_DEV.DBT_DEV.FCT_DIVIDEND_EXPOSURE"


def balances(cursor, business_date, opening_date, scenario):
    for day, source in ((opening_date, "opening_bank"), (business_date, "oms")):
        ready, message = check_source(cursor, day, scenario, source)
        if not ready:
            raise ValueError(message)

    cursor.execute(
        "SELECT r.payload:account_id::varchar, r.payload:currency::varchar, "
        "r.payload:closing_balance::varchar FROM " + OPENING + " r "
        "JOIN " + DELIVERIES + " d ON d.source_name = 'opening_bank' "
        "AND d.scenario_id = %s AND d.business_date = TO_DATE(%s) "
        "AND d.status = 'LOADED' AND ENDSWITH(r.source_file, d.stage_path)",
        (scenario, opening_date)
    )
    cash = {}
    for account, currency, amount in cursor.fetchall():
        if not account or account in cash or currency != "USD":
            raise ValueError("Bad opening bank account or currency")
        cash[account] = Decimal(str(amount))
        if not cash[account].is_finite():
            raise ValueError("Invalid opening bank balance")
    if not cash:
        raise ValueError("No opening bank accounts")

    # No simulated bank payment exists for dividends yet. Do not call an
    # expected dividend a bank receipt.
    cursor.execute(
        "SELECT COUNT(*) FROM " + EXPOSURE + " WHERE scenario_id = %s "
        "AND pay_date <= TO_DATE(%s) AND expected_cash_usd <> 0",
        (scenario, business_date)
    )
    if cursor.fetchone()[0]:
        raise ValueError("Dividend payment evidence is needed for the bank statement")

    cursor.execute(
        "SELECT r.payload:execution_id::varchar, r.payload:account_id::varchar, "
        "r.payload:side::varchar, r.payload:quantity::varchar, "
        "r.payload:execution_price::varchar, r.payload:currency::varchar "
        "FROM " + TRADES + " r JOIN " + DELIVERIES + " d "
        "ON d.source_name = 'oms' AND d.scenario_id = %s "
        "AND d.status = 'SUBMITTED' AND d.business_date > TO_DATE(%s) "
        "AND d.business_date <= TO_DATE(%s) "
        "AND ENDSWITH(r.source_file, d.stage_path) "
        "WHERE r.payload:execution_status::varchar = 'ACTIVE' "
        "AND TRY_TO_DATE(r.payload:settlement_due::varchar) <= TO_DATE(%s)",
        (scenario, opening_date, business_date, business_date)
    )
    seen = set()
    for execution_id, account, side, quantity, price, currency in cursor.fetchall():
        if not execution_id or execution_id in seen or account not in cash or currency != "USD":
            raise ValueError("Repeated or invalid trade in the bank ledger")
        if side not in ("BUY", "SELL"):
            raise ValueError("Bad trade side in the bank ledger")
        shares = Decimal(str(quantity))
        trade_price = Decimal(str(price))
        if not shares.is_finite() or not trade_price.is_finite() or shares <= 0 or trade_price <= 0:
            raise ValueError("Bad trade quantity or price in the bank ledger")
        amount = shares * trade_price
        if amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Trade cash has more than two decimal places")
        cash[account] += -amount if side == "BUY" else amount
        seen.add(execution_id)
    return {account: amount.quantize(Decimal("0.01")) for account, amount in cash.items()}


def write_statement(data_dir, business_date, scenario, cash):
    path = data_dir / "bank_inputs" / scenario / business_date / "statement.csv"
    lines = ["account_id,currency,closing_balance\n"]
    for account in sorted(cash):
        lines.append("{},USD,{:.2f}\n".format(account, cash[account]))
    content = "".join(lines)
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
            cash = balances(cursor, business_date, opening_date, scenario)
            statement = write_statement(data_dir, business_date, scenario, cash)
            item = bank_statements.prepare(statement, data_dir, business_date, scenario)
            print("Prepared {} bank balances for {}".format(item["rows"], business_date))
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
