"""Write the next fictional trading day from the last validated close."""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from pipeline.sample_close import TRADES, save
from pipeline.us_equity_calendar import (
    is_market_day, is_settlement_day, next_settlement_day, previous_market_day
)


NAV = "NORTHBRIDGE_DEV.DBT_DEV.FCT_NAV_DAILY"
RUNS = "NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS"
PRICES = "NORTHBRIDGE_DEV.RAW.DAILY_PRICE_EVENTS"
OMS = "NORTHBRIDGE_DEV.RAW.DAILY_OMS_EVENTS"

# The first four names are the pilot. From October 14, each account trades
# four names per session from a wider, fixed equity list.
EXPANDED_FROM = date(2026, 10, 14)
ORDER_BOOK = {
    "SIM-ACCOUNT-01": (
        ("AAPL", "BUY", 60, 8), ("AMZN", "SELL", 80, -6),
        ("GOOGL", "BUY", 70, 5), ("META", "SELL", 30, -7),
        ("NVDA", "BUY", 90, 4), ("V", "SELL", 55, -5),
        ("MA", "BUY", 35, 6), ("COST", "SELL", 25, -4),
        ("HD", "BUY", 75, 3), ("MCD", "SELL", 80, -3),
    ),
    "SIM-ACCOUNT-02": (
        ("MSFT", "BUY", 45, 5), ("KO", "SELL", 170, -4),
        ("JPM", "BUY", 65, 6), ("BAC", "SELL", 350, -6),
        ("XOM", "BUY", 125, 4), ("JNJ", "SELL", 85, -4),
        ("PG", "BUY", 130, 3), ("WMT", "SELL", 180, -3),
        ("PEP", "BUY", 160, 5), ("UNH", "SELL", 55, -5),
    ),
}


def trades_for_day(day):
    if day < EXPANDED_FROM:
        return TRADES
    sessions = 0
    current = EXPANDED_FROM
    while current < day:
        if is_market_day(current):
            sessions += 1
        current += timedelta(days=1)
    orders = []
    for account, names in ORDER_BOOK.items():
        start = sessions * 4
        for number in range(4):
            orders.append((account,) + names[(start + number) % len(names)])
    return tuple(orders)


def prior_close(cursor, business_date, scenario):
    cursor.execute(
        "SELECT MAX(business_date) FROM " + RUNS +
        " WHERE scenario_id = %s AND business_date < TO_DATE(%s) "
        "AND status = 'VALIDATED'",
        (scenario, business_date)
    )
    row = cursor.fetchone()
    if not row or row[0] is None:
        raise ValueError("No earlier validated NAV for this scenario")
    previous = row[0]
    if previous != previous_market_day(date.fromisoformat(business_date)):
        raise ValueError("Previous market day has no validated close; recover that date first")
    cursor.execute(
        "SELECT COUNT(*) FROM " + NAV +
        " WHERE scenario_id = %s AND valuation_date = %s AND nav_usd IS NOT NULL",
        (scenario, previous)
    )
    if cursor.fetchone()[0] != 2:
        raise ValueError("Previous close does not have two account NAVs")
    return previous.isoformat()


def prior_prices(cursor, previous, business_date):
    tickers = sorted({trade[1] for trade in trades_for_day(date.fromisoformat(business_date))})
    cursor.execute(
        "SELECT p.payload:universe_ticker::varchar, "
        "TRY_TO_DECIMAL(p.payload:close_price::varchar, 38, 9) "
        "FROM " + PRICES + " p "
        "JOIN NORTHBRIDGE_DEV.RAW.DAILY_DELIVERIES d "
        "ON d.source_name = 'prices' AND d.scenario_id = 'massive' "
        "AND d.status = 'LOADED' AND d.business_date = TO_DATE(%s) "
        "AND ENDSWITH(p.source_file, d.stage_path) "
        "WHERE p.payload:universe_ticker::varchar IN (" +
        ", ".join(["%s"] * len(tickers)) + ")",
        (previous,) + tuple(tickers)
    )
    rows = cursor.fetchall()
    if len(rows) != len(tickers) or {r[0] for r in rows} != set(tickers):
        raise ValueError("Previous close prices are incomplete or repeated")
    prices = {ticker: Decimal(str(price)) for ticker, price in rows}
    if any(price <= 0 for price in prices.values()):
        raise ValueError("Previous close price is not positive")
    return prices


def unsettled_trades(cursor, business_date, scenario):
    if not is_settlement_day(date.fromisoformat(business_date)):
        return []
    cursor.execute(
        "SELECT payload:execution_id::varchar, payload:account_id::varchar, "
        "payload:instrument_id::varchar, payload:side::varchar, "
        "payload:quantity::varchar, payload:execution_price::varchar, "
        "payload:settlement_due::varchar "
        "FROM " + OMS + " WHERE payload:scenario_id::varchar = %s "
        "AND TRY_TO_DATE(payload:settlement_due::varchar) <= TO_DATE(%s) "
        "AND TRY_TO_DATE(payload:business_date::varchar) < TO_DATE(%s) "
        "AND payload:execution_status::varchar = 'ACTIVE' "
        "ORDER BY payload:execution_id::varchar",
        (scenario, business_date, business_date)
    )
    trades = cursor.fetchall()
    cursor.execute(
        "SELECT DISTINCT payload:execution_id::varchar "
        "FROM NORTHBRIDGE_DEV.RAW.DAILY_SETTLEMENT_EVENTS "
        "WHERE payload:scenario_id::varchar = %s "
        "AND payload:settlement_status::varchar = 'SETTLED' "
        "AND TRY_TO_DATE(payload:settlement_date::varchar) < TO_DATE(%s)",
        (scenario, business_date)
    )
    done = {row[0] for row in cursor.fetchall()}
    ids = [row[0] for row in trades]
    if len(ids) != len(set(ids)):
        raise ValueError("Repeated execution in RAW")
    return [row for row in trades if row[0] not in done]


def write_day(business_date, scenario, data_dir, previous, closes, due_trades):
    day = date.fromisoformat(business_date)
    if previous >= business_date or not is_market_day(day):
        raise ValueError("Expected a market day after the previous close")
    if due_trades and not is_settlement_day(day):
        raise ValueError("Cannot confirm settlements on a settlement holiday")
    planned = trades_for_day(day)
    missing = sorted({trade[1] for trade in planned} - set(closes))
    if missing:
        raise ValueError("Previous close missing for {}".format(", ".join(missing)))
    due = next_settlement_day(day).isoformat()
    trades = []
    for number, (account, ticker, side, quantity, offset) in enumerate(planned, 1):
        price = (closes[ticker] * (Decimal(1) + Decimal(offset) / 10000)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
        executed = datetime.combine(day, time(15, number), timezone.utc)
        key = "{}-{:02d}".format(day.strftime("%Y%m%d"), number)
        trades.append({
            "schema_version": 1, "event_id": "SIM-EVENT-" + key,
            "event_type": "EXECUTION_REPORTED", "source_system": "simulated_oms",
            "scenario_id": scenario, "is_simulated": True,
            "occurred_at": executed.isoformat(),
            "published_at": (executed + timedelta(milliseconds=60)).isoformat(),
            "executed_at": executed.isoformat(), "business_date": business_date,
            "execution_id": "SIM-EXEC-" + key, "execution_version": 1,
            "execution_status": "ACTIVE", "order_id": "SIM-ORDER-" + key,
            "fund_id": "NORTHBRIDGE", "account_id": account,
            "broker_id": "SIM-BROKER-01", "instrument_id": ticker + ".US",
            "market_ticker": ticker, "side": side, "quantity": str(quantity),
            "execution_price": str(price), "currency": "USD",
            "settlement_due": due, "price_method": "prior_close_with_fictional_offset",
            "reference_price_date": previous,
            "reference_close_price": str(closes[ticker]), "price_offset_bps": offset,
        })
        if day >= EXPANDED_FROM:
            trades[-1]["simulator_plan_id"] = "equity_20_20261014"
    save(data_dir / "daily_oms" / scenario / business_date, "oms.jsonl", trades,
         {"business_date": business_date, "scenario_id": scenario,
          "is_simulated": True, "source_system": "simulated_oms",
          "delivery_id": "oms-{}-{}".format(scenario, business_date),
          "reference_price_date": previous, "settlement_due": due})

    settlements = []
    for number, (execution_id, account, instrument, side, quantity, price, _) in enumerate(due_trades, 1):
        settled = datetime.combine(day, time(18, 0), timezone.utc) + timedelta(seconds=number)
        cash = Decimal(str(quantity)) * Decimal(str(price))
        if side == "BUY":
            cash = -cash
        elif side != "SELL":
            raise ValueError("Bad trade side for settlement")
        key = "{}-{:02d}".format(day.strftime("%Y%m%d"), number)
        settlements.append({
            "schema_version": 1, "event_id": "SIM-SETTLEMENT-EVENT-" + key,
            "event_type": "SETTLEMENT_CONFIRMED", "source_system": "simulated_custodian",
            "scenario_id": scenario, "is_simulated": True,
            "settled_at": settled.isoformat(),
            "published_at": (settled + timedelta(seconds=30)).isoformat(),
            "settlement_date": business_date,
            "settlement_id": "SIM-SETTLEMENT-" + key,
            "settlement_status": "SETTLED", "execution_id": execution_id,
            "account_id": account, "broker_id": "SIM-BROKER-01",
            "fund_id": "NORTHBRIDGE", "instrument_id": instrument,
            "side": side, "settled_quantity": str(quantity),
            "cash_amount": str(cash), "currency": "USD",
        })
    suffix = "" if settlements else "-empty"
    save(data_dir / "daily_settlements" / scenario / business_date,
         "settlements.jsonl", settlements,
         {"business_date": business_date, "settlement_date": business_date,
          "scenario_id": scenario, "is_simulated": True,
          "source_system": "simulated_custodian",
          "delivery_id": "settlement-{}-{}{}".format(scenario, business_date, suffix)})
    return len(trades), len(settlements)
