"""Calculate the five-day test close from Snowpipe RAW and saved market prices."""

from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fund_pipeline.daily_continuation import calculate
from scripts.check_daily_oms_pilot import connect
from simulation.daily_oms import price_rows, write_once

CONFIG = ROOT / 'config/two_year_pilot.json'
OUT = ROOT / 'data/daily_close/bank_opening_v1'


def saved_delivery(folder, filename):
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    raw = (folder / filename).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest['files'][filename]:
        raise ValueError(f'Saved file changed: {folder}')
    events = [json.loads(line) for line in raw.splitlines()]
    if len(events) != manifest['record_count']:
        raise ValueError(f'Saved row count changed: {folder}')
    return manifest, events


def loaded_events(cursor, table, delivery_id, expected):
    cursor.execute(f'''
        select payload::varchar from NORTHBRIDGE_DEV.RAW.{table}
        where delivery_id = %s order by source_row_number
    ''', (delivery_id,))
    rows = [json.loads(row[0]) for row in cursor.fetchall()]
    if len(rows) != len(expected):
        raise ValueError(f'{table}/{delivery_id}: RAW row count differs')
    key = 'event_id' if table in ('OMS_EVENTS', 'SETTLEMENT_EVENTS',
                                  'DIVIDEND_PAYMENT_EVENTS') else 'record_id'
    by_id = {row[key]: row for row in rows}
    if len(by_id) != len(rows) or by_id != {row[key]: row for row in expected}:
        raise ValueError(f'{table}/{delivery_id}: RAW differs from saved file')
    source_names = {'OMS_EVENTS': 'oms_events',
                    'SETTLEMENT_EVENTS': 'settlement_events',
                    'FUND_ADMIN_EVENTS': 'fund_admin',
                    'BANK_CASH_STATEMENTS': 'bank_cash',
                    'DIVIDEND_PAYMENT_EVENTS': 'dividend_payments'}
    cursor.execute('''
        select expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
        where source_name = %s and delivery_id = %s
    ''', (source_names[table], delivery_id))
    if cursor.fetchall() != [(len(expected), len(expected), 'READY')]:
        raise ValueError(f'{table}/{delivery_id}: receipt is not READY')
    return rows


def opening_from_statements(day, scenario, accounts, admin, bank, delivery_ids):
    if len(admin) != len(accounts) or len(bank) != len(accounts):
        raise ValueError('Opening statements do not cover every account once')
    subscriptions = {row['account_id']: row for row in admin}
    balances = {row['account_id']: row for row in bank}
    if (len(subscriptions) != len(admin) or len(balances) != len(bank)
            or set(subscriptions) != set(accounts) or set(balances) != set(accounts)):
        raise ValueError('Opening accounts are missing or repeated')
    cash = []
    for account in accounts:
        subscription = subscriptions[account]
        balance = balances[account]
        if (subscription['scenario_id'] != scenario or balance['scenario_id'] != scenario
                or subscription['event_date'] != day or balance['statement_date'] != day
                or subscription['event_type'] != 'INVESTOR_SUBSCRIPTION'
                or subscription['source_system'] != 'simulated_fund_administrator'
                or balance['source_system'] != 'simulated_bank'
                or subscription['is_simulated'] is not True
                or balance['is_simulated'] is not True
                or subscription['currency'] != 'USD' or balance['currency'] != 'USD'):
            raise ValueError(f'Opening source or date differs for {account}')
        published = datetime.fromisoformat(balance['published_at'].replace('Z', '+00:00'))
        if published.date().isoformat() != day:
            raise ValueError(f'Opening bank statement published on another date: {account}')
        amount = Decimal(subscription['amount'])
        reported = Decimal(balance['closing_balance'])
        if not amount.is_finite() or amount <= 0 or amount != reported:
            raise ValueError(f'Opening capital and bank cash differ for {account}')
        cash.append(dict(account_id=account, reported_settled_cash=str(reported),
                         dividend_receivable='0', short_dividend_payable='0',
                         expense_payable='0'))
    opening = {'business_date': day, 'scenario_id': scenario,
               'source_status': 'UNAPPROVED_TEST',
               'source_delivery_ids': delivery_ids,
               'cash': cash, 'positions': [], 'obligations': [],
               'prior_execution_ids': []}
    digest = hashlib.sha256(json.dumps(opening, sort_keys=True).encode()).hexdigest()
    opening['opening_id'] = 'opening-' + digest[:24]
    return opening


def security_map(cursor, day, tickers):
    cursor.execute('''
        select ticker, security_id
        from NORTHBRIDGE_DEV.DBT_DEV.DIM_INSTRUMENT
        where %s between valid_from and valid_to
    ''', (day,))
    result = {}
    for ticker, security in cursor.fetchall():
        if ticker not in tickers:
            continue
        if ticker in result:
            raise ValueError(f'Multiple securities for {ticker} on {day}')
        result[ticker] = security
    if set(result) != set(tickers):
        raise ValueError(f'Missing instrument identities: {set(tickers) - set(result)}')
    return result


def check_actions(cursor, day, tickers):
    cursor.execute('''
        select a.ticker, a.event_id
        from NORTHBRIDGE_DEV.DBT_DEV.STG_CORPORATE_ACTIONS a
        join NORTHBRIDGE_DEV.DBT_DEV.APPROVED_CORPORATE_ACTIONS r
          on a.event_id = r.event_id
        where a.ex_dividend_date = %s or a.execution_date = %s
    ''', (day, day))
    active = [(ticker, event_id) for ticker, event_id in cursor.fetchall() if ticker in tickers]
    if active:
        raise ValueError(f'Corporate actions need accounting on {day}: {active}')


def check_settlements(day, confirmations, prior_trades):
    due = {execution_id: row for execution_id, row in prior_trades.items()
           if row['settlement_due'] == day}
    received = {row['execution_id']: row for row in confirmations}
    if len(received) != len(confirmations) or set(received) != set(due):
        raise ValueError(f'{day}: custodian confirmations differ from trades due today')
    for execution_id, row in received.items():
        trade = due[execution_id]
        amount = Decimal(trade['quantity']) * Decimal(trade['execution_price'])
        if trade['side'] == 'BUY':
            amount = -amount
        if (row['account_id'] != trade['account_id']
                or row['instrument_id'] != trade['instrument_id']
                or row['side'] != trade['side']
                or Decimal(row['settled_quantity']) != Decimal(trade['quantity'])
                or Decimal(row['cash_amount']) != amount):
            raise ValueError(f'{day}: custodian confirmation differs from {execution_id}')


def next_opening(close, scenario, source_delivery_ids):
    accounts = close['accounts']
    opening = {
        'business_date': close['business_date'], 'scenario_id': scenario,
        'source_status': 'UNAPPROVED_TEST',
        'source_delivery_ids': source_delivery_ids,
        'cash': [dict(account_id=account, reported_settled_cash=str(row['cash']),
                      dividend_receivable='0', short_dividend_payable='0',
                      expense_payable='0') for account, row in sorted(accounts.items())],
        'positions': [dict(account_id=account, security_id=security,
                           closing_quantity=str(quantity))
                      for (account, security), quantity in sorted(close['positions'].items())],
        'obligations': [close['open_obligations'][key]
                        for key in sorted(close['open_obligations'])],
        'prior_execution_ids': close['prior_execution_ids'],
    }
    digest = hashlib.sha256(json.dumps(opening, sort_keys=True).encode()).hexdigest()
    opening['opening_id'] = 'opening-' + digest[:24]
    return opening


def run():
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    scenario = config['scenario_id']
    if hashlib.sha256((ROOT / config['price_file']).read_bytes()).hexdigest() != config['price_sha256']:
        raise ValueError('Saved market price snapshot changed')
    sessions, market = price_rows(ROOT / config['price_file'], set(config['tickers']))
    days = [day for day in sessions if config['start_date'] <= day <= config['end_date']]
    opening_day = sessions[sessions.index(days[0]) - 1]
    connection = connect()
    prior_trades = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            folder = ROOT / 'data/daily_opening' / scenario / opening_day
            admin_manifest, admin_saved = saved_delivery(folder / 'fund_admin', 'events.jsonl')
            bank_manifest, bank_saved = saved_delivery(folder / 'bank_cash', 'balances.jsonl')
            admin = loaded_events(cursor, 'FUND_ADMIN_EVENTS', admin_manifest['delivery_id'], admin_saved)
            bank = loaded_events(cursor, 'BANK_CASH_STATEMENTS', bank_manifest['delivery_id'], bank_saved)
            source_ids = {'fund_admin': admin_manifest['delivery_id'],
                          'bank_cash': bank_manifest['delivery_id']}
            opening = opening_from_statements(opening_day, scenario, config['accounts'],
                                              admin, bank, source_ids)
            for day in days:
                oms_manifest, oms_saved = saved_delivery(
                    ROOT / 'data/daily_oms' / scenario / day, 'oms.jsonl')
                trades = loaded_events(cursor, 'OMS_EVENTS', oms_manifest['delivery_id'], oms_saved)
                folder = ROOT / 'data/daily_settlements' / scenario / day
                settlements = []
                if folder.exists():
                    manifest, saved = saved_delivery(folder, 'settlements.jsonl')
                    settlements = loaded_events(cursor, 'SETTLEMENT_EVENTS',
                                                manifest['delivery_id'], saved)
                check_settlements(day, settlements, prior_trades)
                identities = security_map(cursor, day, config['tickers'])
                check_actions(cursor, day, config['tickers'])
                prices = {identities[ticker]: str(market[(day, ticker)])
                          for ticker in config['tickers']}
                events = []
                for trade in trades:
                    events.append(dict(record_type='EXECUTION', event_id=trade['event_id'],
                                       business_date=day, scenario_id=scenario,
                                       account_id=trade['account_id'],
                                       security_id=identities[trade['market_ticker']],
                                       execution_id=trade['execution_id'],
                                       execution_version=trade['execution_version'],
                                       published_at=trade['published_at'],
                                       side=trade['side'], quantity=trade['quantity'],
                                       execution_price=trade['execution_price'],
                                       settlement_due=trade['settlement_due'], currency='USD'))
                for settlement in settlements:
                    events.append(dict(record_type='SETTLEMENT', event_id=settlement['event_id'],
                                       business_date=day, scenario_id=scenario,
                                       account_id=settlement['account_id'],
                                       execution_id=settlement['execution_id'],
                                       cash_amount=settlement['cash_amount'],
                                       settled_at=settlement['settled_at'],
                                       published_at=settlement['published_at'], currency='USD'))
                delivery = {'opening_id': opening['opening_id'], 'business_date': day,
                            'cutoff': day + 'T23:00:00+00:00', 'events': events}
                close = calculate(opening, delivery, prices)
                output = {'business_date': day, 'scenario_id': scenario,
                          'status': 'UNAPPROVED_TEST', 'opening_id': opening['opening_id'],
                          'opening_delivery_ids': source_ids,
                          'oms_delivery_id': oms_manifest['delivery_id'],
                          'settlement_count': len(settlements),
                          'accounts': {account: {key: str(value) for key, value in values.items()}
                                       for account, values in close['accounts'].items()},
                          'open_obligations': len(close['open_obligations'])}
                target = OUT / scenario / day
                write_once(target / 'close.json',
                           (json.dumps(output, indent=2, sort_keys=True) + '\n').encode())
                opening = next_opening(close, scenario, source_ids)
                write_once(target / 'next_opening.json',
                           (json.dumps(opening, indent=2, sort_keys=True) + '\n').encode())
                prior_trades.update({trade['execution_id']: trade for trade in trades})
                print(f"{day}: {len(trades)} fills, {len(settlements)} settlements, "
                      f"{len(close['open_obligations'])} open; "
                      + ', '.join(f'{account} NAV {values["nav"]}'
                                  for account, values in output['accounts'].items()))
    finally:
        connection.close()


if __name__ == '__main__':
    run()
