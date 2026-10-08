"""Build an unapproved two-year close from Snowflake RAW and reviewed mappings."""

from collections import defaultdict
import argparse
import csv
from decimal import Decimal
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fund_pipeline.two_year_close import calculate
from scripts.check_daily_oms_pilot import connect
from scripts.close_daily_pilot import loaded_events, opening_from_statements, saved_delivery
from simulation.daily_oms import write_once


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def feed(cursor, table, source_name, directory, filename, date_field, scenario):
    expected = {}
    digests = {}
    for folder in sorted(path for path in directory.iterdir() if path.is_dir()):
        manifest, rows = saved_delivery(folder, filename)
        delivery_id = manifest['delivery_id']
        digests[delivery_id] = manifest['files'][filename]
        for row in rows:
            event_id = row['event_id']
            if event_id in expected:
                raise ValueError(f'Duplicate saved event: {event_id}')
            expected[event_id] = (delivery_id, row)
    scope = ('scenario_id = %s' if table == 'OMS_EVENTS'
             else 'payload:scenario_id::varchar = %s')
    cursor.execute(f'''
        select delivery_id, payload::varchar
        from NORTHBRIDGE_DEV.RAW.{table} where {scope}
    ''', (scenario,))
    loaded = {}
    for delivery_id, payload in cursor.fetchall():
        row = json.loads(payload)
        event_id = row['event_id']
        if event_id in loaded:
            raise ValueError(f'Duplicate RAW event: {event_id}')
        loaded[event_id] = (delivery_id, row)
    if loaded != expected:
        raise ValueError(f'{table} does not match the saved daily files')
    cursor.execute('''
        select delivery_id, manifest_sha256, expected_rows, received_rows, delivery_status
        from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES where source_name = %s
    ''', (source_name,))
    receipts = {row[0]: row[1:] for row in cursor.fetchall()}
    for delivery_id, digest in digests.items():
        count = sum(item[0] == delivery_id for item in expected.values())
        if receipts.get(delivery_id) != (digest, count, count, 'READY'):
            raise ValueError(f'Delivery receipt is not READY: {delivery_id}')
    by_day = defaultdict(list)
    for _, row in loaded.values():
        by_day[row[date_field]].append(row)
    return by_day, len(loaded), len(digests)


def market_prices(cursor, tickers):
    marks = ', '.join('%s' for _ in tickers)
    cursor.execute(f'''
        select p.valuation_date, p.universe_ticker, i.security_id, p.close_price
        from NORTHBRIDGE_DEV.DBT_DEV.STG_HISTORICAL_PRICES p
        join NORTHBRIDGE_DEV.DBT_DEV.DIM_INSTRUMENT i
          on p.universe_ticker = i.ticker
         and p.valuation_date between i.valid_from and i.valid_to
         and (p.share_class_figi = i.share_class_figi or p.share_class_figi is null)
        where p.universe_ticker in ({marks})
          and p.currency = 'USD' and p.price_basis = 'unadjusted'
    ''', tuple(tickers))
    prices = defaultdict(dict)
    identities = {}
    for day, ticker, security, close in cursor.fetchall():
        day = day.isoformat()
        if security in prices[day] or (day, ticker) in identities or close is None or close <= 0:
            raise ValueError(f'Duplicate or invalid market price: {ticker} on {day}')
        prices[day][security] = close
        identities[(day, ticker)] = security
    sessions = sorted(prices)
    if len(sessions) != 500 or any(len(prices[day]) != len(tickers) for day in sessions):
        raise ValueError('The 20-stock, 500-date market matrix is incomplete')
    return sessions, prices, identities


def dividend_candidates(cursor, tickers, sessions, identities):
    review_rows = read_csv(ROOT / 'data/two_year_dividend_review.csv')
    review = {row['event_id']: row for row in review_rows}
    if len(review) != len(review_rows):
        raise ValueError('Duplicate event ID in dividend review queue')
    approved_rows = read_csv(ROOT / 'dbt/seeds/approved_corporate_actions.csv')
    approved = {row['event_id'] for row in approved_rows}
    if len(approved) != len(approved_rows):
        raise ValueError('Duplicate event ID in approved action seed')
    marks = ', '.join('%s' for _ in tickers)
    cursor.execute(f'''
        select event_id, ticker, ex_dividend_date, pay_date, currency, cash_amount
        from NORTHBRIDGE_DEV.DBT_DEV.STG_CORPORATE_ACTIONS
        where action_type = 'dividends' and ticker in ({marks})
          and ex_dividend_date between %s and %s
    ''', (*tickers, sessions[0], sessions[-1]))
    actions = defaultdict(list)
    found = set()
    for event_id, ticker, ex_date, pay_date, currency, amount in cursor.fetchall():
        day = ex_date.isoformat()
        if event_id in found or event_id not in review or day not in sessions:
            raise ValueError(f'Unknown, repeated or off-calendar action: {event_id}')
        row = review[event_id]
        security = identities[(day, ticker)]
        if (row['security_id'] != security or row['ex_dividend_date'] != day
                or row['pay_date'] != pay_date.isoformat()
                or Decimal(row['cash_per_share_usd']) != amount
                or (row['review_status'] == 'APPROVED_IN_SEED') != (event_id in approved)
                or currency != 'USD'):
            raise ValueError(f'Corporate action differs from review queue: {event_id}')
        actions[day].append(dict(event_id=event_id, security_id=security,
                                 ticker=ticker,
                                 cash_amount=str(amount), currency=currency,
                                 pay_date=row['pay_date'],
                                 review_status=row['review_status']))
        found.add(event_id)
    if found != set(review):
        raise ValueError('Corporate-action review queue differs from Snowflake')
    return actions


def security_transfers(cursor, sessions):
    rows = read_csv(ROOT / 'config/two_year_security_transfers.csv')
    cursor.execute('''
        select security_id, predecessor_security_id, valid_from
        from NORTHBRIDGE_DEV.DBT_DEV.DIM_INSTRUMENT
        where predecessor_security_id is not null
    ''')
    known = {(security, predecessor, day.isoformat())
             for security, predecessor, day in cursor.fetchall()}
    transfers = defaultdict(list)
    for row in rows:
        key = (row['security_id'], row['predecessor_security_id'], row['effective_date'])
        if key not in known or row['effective_date'] not in sessions:
            raise ValueError(f'Unmatched security transfer: {key}')
        transfers[row['effective_date']].append(row)
    return transfers


def csv_bytes(rows):
    handle = StringIO(newline='')
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return handle.getvalue().encode('utf-8')


def payment_pilot(cursor, scenario):
    folder = ROOT / 'data/dividend_payment_pilot' / scenario / '2025-02-07'
    payment_manifest, saved_payments = saved_delivery(folder / 'custodian', 'payments.jsonl')
    bank_manifest, saved_bank = saved_delivery(folder / 'bank', 'balances.jsonl')
    if (payment_manifest['scenario_id'] != scenario or bank_manifest['scenario_id'] != scenario
            or payment_manifest['business_date'] != '2025-02-07'
            or bank_manifest['business_date'] != '2025-02-07'):
        raise ValueError('Dividend pilot belongs to another scenario or date')
    evidence = payment_manifest['source_evidence']
    if (evidence != bank_manifest['source_evidence']
            or hashlib.sha256((ROOT / 'dbt/seeds/approved_corporate_actions.csv').read_bytes()).hexdigest()
            != evidence['approved_actions_sha256']):
        raise ValueError('Dividend pilot review evidence changed')
    old_folder = ROOT / 'data/two_year_close/provisional_v2'
    for name, field in (('daily.csv', 'daily_sha256'),
                        ('dividend_entitlements.csv', 'entitlements_sha256')):
        if hashlib.sha256((old_folder / name).read_bytes()).hexdigest() != evidence[field]:
            raise ValueError(f'Dividend pilot input changed: {name}')
    for subfolder, manifest in (('custodian', payment_manifest), ('bank', bank_manifest)):
        digest = hashlib.sha256((folder / subfolder / 'manifest.json').read_bytes()).hexdigest()
        cursor.execute('''
            select manifest_sha256 from NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
            where delivery_id = %s
        ''', (manifest['delivery_id'],))
        if cursor.fetchall() != [(digest,)]:
            raise ValueError(f'Dividend pilot receipt hash differs: {subfolder}')
    payments = loaded_events(cursor, 'DIVIDEND_PAYMENT_EVENTS',
                             payment_manifest['delivery_id'], saved_payments)
    bank = loaded_events(cursor, 'BANK_CASH_STATEMENTS',
                         bank_manifest['delivery_id'], saved_bank)
    if len(payments) != 2 or len(bank) != 2:
        raise ValueError('Dividend pilot needs two payment and bank rows')
    if any(row['scenario_id'] != scenario for row in payments + bank):
        raise ValueError('Dividend pilot payload belongs to another scenario')
    return {'2025-02-07': payments}, bank, {
        'dividend_payments': payment_manifest['delivery_id'],
        'bank_cash': bank_manifest['delivery_id'],
    }


def check_payment_result(daily, entitlements, bank, scenario):
    old_folder = ROOT / 'data/two_year_close/provisional_v2'
    old_manifest = json.loads((old_folder / 'manifest.json').read_text(encoding='utf-8'))
    old_path = old_folder / 'daily.csv'
    if (old_manifest['scenario_id'] != scenario or
            hashlib.sha256(old_path.read_bytes()).hexdigest() != old_manifest['files']['daily.csv']['sha256']):
        raise ValueError('Original v2 close changed')
    original = read_csv(old_path)
    if len(original) != len(daily):
        raise ValueError('Payment close changed the number of daily rows')
    approved = [row for row in entitlements if row['event_id'] ==
                'Ec6372be9137e6a822fd370e8f0738fc31cfb9db56ee95abb2ee9b45f3022db0b']
    if len(approved) != 2 or any(row['payment_status'] != 'MATCHED' for row in approved):
        raise ValueError('The reviewed Mastercard entitlement did not clear')
    paid = {row['account_id']: Decimal(row['gross_amount_usd']) for row in approved}
    for before, after in zip(original, daily):
        if ((before['business_date'], before['account_id']) !=
                (after['business_date'], after['account_id'])
                or Decimal(before['illustrative_nav_usd']) != Decimal(after['illustrative_nav_usd'])):
            raise ValueError('Dividend payment changed accrued NAV or close dates')
        difference = paid[after['account_id']] if after['business_date'] >= '2025-02-07' else Decimal(0)
        if (Decimal(after['settled_cash_usd']) - Decimal(before['settled_cash_usd']) != difference
                or Decimal(before['dividend_receivable_unconfirmed_usd'])
                   - Decimal(after['dividend_receivable_unconfirmed_usd']) != difference):
            raise ValueError('Payment did not carry forward from receivable to cash')
    on_day = {row['account_id']: row for row in daily if row['business_date'] == '2025-02-07'}
    bank_by_account = {row['account_id']: row for row in bank}
    if len(on_day) != 2 or len(bank_by_account) != len(bank) or set(on_day) != set(bank_by_account):
        raise ValueError('Payment-day bank account coverage differs')
    for account, row in on_day.items():
        statement = bank_by_account[account]
        if (statement['statement_date'] != '2025-02-07'
                or statement['currency'] != 'USD'
                or statement['source_system'] != 'simulated_bank'
                or statement['is_simulated'] is not True
                or Decimal(row['settled_cash_usd']) != Decimal(statement['closing_balance'])):
            raise ValueError(f'Payment-day bank cash differs: {account}')


def check_review_split(daily, entitlements, scenario):
    old_folder = ROOT / 'data/two_year_close/provisional_v2_paid_ma'
    old_manifest = json.loads((old_folder / 'manifest.json').read_text(encoding='utf-8'))
    old_path = old_folder / 'daily.csv'
    if (old_manifest['scenario_id'] != scenario
            or hashlib.sha256(old_path.read_bytes()).hexdigest()
            != old_manifest['files']['daily.csv']['sha256']):
        raise ValueError('Payment-aware v2 close changed')
    old_rows = read_csv(old_path)
    if len(old_rows) != len(daily):
        raise ValueError('Review split changed the number of close rows')
    for old, row in zip(old_rows, daily):
        if any(row[key] != value for key, value in old.items()):
            raise ValueError('Review split changed an existing close value')
        reviewed_receivable = Decimal(row['reviewed_dividend_receivable_usd'])
        reviewed_payable = Decimal(row['reviewed_short_dividend_payable_usd'])
        pending_receivable = Decimal(row['pending_dividend_receivable_usd'])
        pending_payable = Decimal(row['pending_short_dividend_payable_usd'])
        impact = Decimal(row['pending_candidate_impact_usd'])
        if (reviewed_receivable + pending_receivable !=
                Decimal(row['dividend_receivable_unconfirmed_usd'])
                or reviewed_payable + pending_payable !=
                Decimal(row['short_dividend_payable_unconfirmed_usd'])
                or impact != pending_receivable - pending_payable
                or impact != Decimal(row['pending_review_dividend_net_usd'])
                or Decimal(row['nav_excluding_pending_actions_usd']) + impact !=
                Decimal(row['illustrative_nav_usd'])):
            raise ValueError('Reviewed and pending balances do not add back to the old close')
    reviewed = {row['event_id'] for row in entitlements
                if row['review_status'] == 'APPROVED_IN_SEED'}
    pending = {row['event_id'] for row in entitlements
               if row['review_status'] == 'PENDING'}
    if len(reviewed) != 1 or len(pending) != 143:
        raise ValueError('Unexpected reviewed or pending action count')
    final_day = daily[-1]['business_date']
    return {'reviewed_event_ids': len(reviewed), 'pending_event_ids': len(pending),
            'last_date': final_day,
            'final_pending_impact_usd_by_account': {
                row['account_id']: row['pending_candidate_impact_usd']
                for row in daily if row['business_date'] == final_day}}


def run(config_path=ROOT / 'config/two_year_replay.json', apply_dividend_pilot=False,
        separate_pending_dividends=False):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    scenario = config['scenario_id']
    if scenario not in ('sim-equity-2024-2026-v1', 'sim-equity-2024-2026-v2'):
        raise ValueError('Unexpected two-year scenario')
    if apply_dividend_pilot and not scenario.endswith('v2'):
        raise ValueError('The dividend payment pilot belongs only to v2')
    if separate_pending_dividends and not apply_dividend_pilot:
        raise ValueError('Review split uses the v2 close with the Mastercard payment applied')
    output_name = ('provisional_v2_review_split' if separate_pending_dividends else
                   'provisional_v2_paid_ma' if apply_dividend_pilot else
                   'provisional_v2' if scenario.endswith('v2') else 'provisional_v1')
    output = ROOT / 'data/two_year_close' / output_name
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE SECONDARY ROLES NONE')
            opening_day = '2024-09-23'
            opening_folder = ROOT / 'data/daily_opening' / scenario / opening_day
            admin_manifest, admin_saved = saved_delivery(opening_folder / 'fund_admin', 'events.jsonl')
            bank_manifest, bank_saved = saved_delivery(opening_folder / 'bank_cash', 'balances.jsonl')
            admin = loaded_events(cursor, 'FUND_ADMIN_EVENTS', admin_manifest['delivery_id'], admin_saved)
            bank = loaded_events(cursor, 'BANK_CASH_STATEMENTS', bank_manifest['delivery_id'], bank_saved)
            opening = opening_from_statements(opening_day, scenario, config['accounts'],
                                              admin, bank, {'fund_admin': admin_manifest['delivery_id'],
                                                            'bank_cash': bank_manifest['delivery_id']})
            trades, trade_count, trade_deliveries = feed(
                cursor, 'OMS_EVENTS', 'oms_events', ROOT / 'data/daily_oms' / scenario,
                'oms.jsonl', 'business_date', scenario)
            settlements, settled_count, settlement_deliveries = feed(
                cursor, 'SETTLEMENT_EVENTS', 'settlement_events',
                ROOT / 'data/daily_settlements' / scenario,
                'settlements.jsonl', 'settlement_date', scenario)
            sessions, prices, identities = market_prices(cursor, config['tickers'])
            if sessions[0] != opening_day or sessions[-1] != '2026-09-21':
                raise ValueError('Unexpected market date range')
            dividends = dividend_candidates(cursor, config['tickers'], sessions, identities)
            transfers = security_transfers(cursor, sessions)
            if apply_dividend_pilot:
                payments, pilot_bank, pilot_deliveries = payment_pilot(cursor, scenario)
            else:
                payments, pilot_bank, pilot_deliveries = {}, [], {}
    finally:
        connection.close()
    initial_cash = {row['account_id']: row['reported_settled_cash'] for row in opening['cash']}
    daily, positions, entitlements, moved = calculate(
        sessions, initial_cash, prices, identities, trades, settlements,
        dividends, transfers, payments, separate_pending_dividends)
    if apply_dividend_pilot:
        check_payment_result(daily, entitlements, pilot_bank, scenario)
    review_split = check_review_split(daily, entitlements, scenario) if separate_pending_dividends else None
    files = {}
    for name, rows in (('daily.csv', daily), ('positions.csv', positions),
                       ('dividend_entitlements.csv', entitlements),
                       ('security_transfers.csv', moved)):
        body = csv_bytes(rows)
        write_once(output / name, body)
        files[name] = {'rows': len(rows), 'sha256': hashlib.sha256(body).hexdigest()}
    manifest = {
        'scenario_id': scenario, 'status': 'PROVISIONAL_UNAPPROVED',
        'market_dates': len(sessions), 'first_date': sessions[0], 'last_date': sessions[-1],
        'oms_events': trade_count, 'oms_deliveries': trade_deliveries,
        'settlement_events': settled_count, 'settlement_deliveries': settlement_deliveries,
        'corporate_action_candidates': sum(map(len, dividends.values())),
        'opening_delivery_ids': opening['source_delivery_ids'],
        'files': files,
        'limitations': ('Only the reviewed Mastercard dividend has a fictional payment and payment-day bank check; '
                        '143 other dividend events are pending review. Most dates have no bank statement. '
                        'No borrow fees or tax.' if apply_dividend_pilot else
                        'Pending dividend reviews, no dividend payment confirmations, no daily bank/fund-admin reconciliation, no borrow fees or tax.'),
    }
    if apply_dividend_pilot:
        manifest['payment_pilot_delivery_ids'] = pilot_deliveries
    if separate_pending_dividends:
        manifest['review_split'] = review_split
        manifest['limitations'] = (
            'NAV excluding pending corporate actions is still provisional: most days lack bank statements, '
            'only the Mastercard payment is confirmed in the fictional feed, and borrow fees and tax are absent.')
    write_once(output / 'manifest.json',
               (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    print(f"{len(daily)} account-day closes, {len(positions)} position rows, "
          f"{len(entitlements)} candidate entitlements; status PROVISIONAL_UNAPPROVED")
    print(output)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/two_year_replay.json')
    parser.add_argument('--apply-dividend-pilot', action='store_true')
    parser.add_argument('--separate-pending-dividends', action='store_true')
    args = parser.parse_args()
    run(args.config.resolve(), args.apply_dividend_pilot, args.separate_pending_dividends)
