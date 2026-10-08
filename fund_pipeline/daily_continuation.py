"""Carry one saved close into the next USD market day."""

from datetime import datetime
from decimal import Decimal


def number(value):
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError('Non-finite amount')
    return result


def latest_executions(events):
    by_execution = {}
    event_ids = set()
    for row in events:
        event_id = row['event_id']
        if event_id in event_ids:
            raise ValueError(f'Duplicate event ID: {event_id}')
        event_ids.add(event_id)
        if row['record_type'] != 'EXECUTION':
            continue
        execution_id = row['execution_id']
        version = int(row['execution_version'])
        if version < 1:
            raise ValueError('Execution version must be positive')
        by_execution.setdefault(execution_id, []).append(row)

    latest = {}
    for execution_id, versions in by_execution.items():
        versions.sort(key=lambda row: int(row['execution_version']))
        if [int(row['execution_version']) for row in versions] != list(range(1, len(versions) + 1)):
            raise ValueError(f'Missing or duplicate correction version: {execution_id}')
        for previous, current in zip(versions, versions[1:]):
            if current.get('supersedes_event_id') != previous['event_id']:
                raise ValueError(f'Broken correction chain: {execution_id}')
            if (current['account_id'], current['security_id']) != (previous['account_id'], previous['security_id']):
                raise ValueError(f'Correction changes trade identity: {execution_id}')
            current_time = datetime.fromisoformat(current['published_at'].replace('Z', '+00:00'))
            previous_time = datetime.fromisoformat(previous['published_at'].replace('Z', '+00:00'))
            if current_time <= previous_time:
                raise ValueError(f'Correction arrived before the record it replaces: {execution_id}')
        latest[execution_id] = versions[-1]
    return latest


def calculate(opening, delivery, prices):
    day = delivery['business_date']
    if day <= opening['business_date']:
        raise ValueError('New close must follow the opening close')
    if delivery['opening_id'] != opening['opening_id']:
        raise ValueError('Delivery names a different opening state')
    events = delivery['events']
    if any(row['business_date'] != day for row in events):
        raise ValueError('Event belongs to another business day')
    cutoff = datetime.fromisoformat(delivery['cutoff'].replace('Z', '+00:00'))
    for row in events:
        if row['record_type'] not in ('EXECUTION', 'SETTLEMENT'):
            raise ValueError(f'Unexpected event type: {row["record_type"]}')
        if (opening.get('scenario_id') is not None
                and row.get('scenario_id') != opening['scenario_id']):
            raise ValueError(f'Event belongs to another scenario: {row["event_id"]}')
        if row.get('currency', 'USD') != 'USD':
            raise ValueError('This continuation handles USD only')
        published = datetime.fromisoformat(row['published_at'].replace('Z', '+00:00'))
        if published > cutoff:
            raise ValueError(f'Event arrived after cutoff: {row["event_id"]}')
        if row['record_type'] == 'SETTLEMENT':
            settled_at = datetime.fromisoformat(row['settled_at'].replace('Z', '+00:00'))
            if settled_at > cutoff:
                raise ValueError(f'Settlement occurred after cutoff: {row["event_id"]}')
            if settled_at > published:
                raise ValueError(f'Settlement published before it occurred: {row["event_id"]}')
    trades = latest_executions(events)
    accounts = {row['account_id']: row for row in opening['cash']}
    positions = {(row['account_id'], row['security_id']): number(row['closing_quantity'])
                 for row in opening['positions']}
    obligations = {row['execution_id']: dict(row) for row in opening['obligations']}
    if len(accounts) != len(opening['cash']) or len(positions) != len(opening['positions']):
        raise ValueError('Duplicate account or opening position')
    if len(obligations) != len(opening['obligations']):
        raise ValueError('Duplicate opening obligation')
    prior_ids = set(opening.get('prior_execution_ids', obligations))
    if not set(obligations).issubset(prior_ids):
        raise ValueError('Opening obligation has no prior execution')
    cash = {account: number(row['reported_settled_cash']) for account, row in accounts.items()}
    dividends = {account: number(row['dividend_receivable']) for account, row in accounts.items()}
    short_dividends = {account: number(row['short_dividend_payable']) for account, row in accounts.items()}
    expenses = {account: number(row['expense_payable']) for account, row in accounts.items()}

    for execution_id, row in trades.items():
        account = row['account_id']
        if account not in accounts or execution_id in prior_ids:
            raise ValueError(f'Unknown account or reused execution ID: {execution_id}')
        quantity = number(row['quantity'])
        price = number(row['execution_price'])
        if quantity <= 0 or price <= 0 or row['side'] not in ('BUY', 'SELL'):
            raise ValueError(f'Invalid trade: {execution_id}')
        sign = 1 if row['side'] == 'BUY' else -1
        key = (account, row['security_id'])
        positions[key] = positions.get(key, Decimal(0)) + sign * quantity
        obligations[execution_id] = dict(account_id=account,
                                         security_id=row['security_id'],
                                         execution_id=execution_id,
                                         settlement_due=row['settlement_due'],
                                         expected_cash=str(-sign * quantity * price))

    settled = set()
    for row in events:
        if row['record_type'] != 'SETTLEMENT':
            continue
        execution_id = row['execution_id']
        if execution_id in settled or execution_id not in obligations:
            raise ValueError(f'Duplicate or unmatched settlement: {execution_id}')
        obligation = obligations[execution_id]
        if row['account_id'] != obligation['account_id']:
            raise ValueError(f'Settlement account differs: {execution_id}')
        amount = number(row['cash_amount'])
        if amount != number(obligation['expected_cash']):
            raise ValueError(f'Settlement amount differs: {execution_id}')
        cash[row['account_id']] += amount
        settled.add(execution_id)
    for execution_id in settled:
        del obligations[execution_id]

    values = {account: Decimal(0) for account in accounts}
    for (account, security), quantity in positions.items():
        if security not in prices:
            raise ValueError(f'Missing close price: {security}')
        price = number(prices[security])
        if price <= 0:
            raise ValueError(f'Invalid close price: {security}')
        values[account] += quantity * price

    result = {}
    for account in accounts:
        open_items = [row for row in obligations.values() if row['account_id'] == account]
        receivables = sum((max(number(row['expected_cash']), Decimal(0)) for row in open_items), Decimal(0))
        payables = sum((max(-number(row['expected_cash']), Decimal(0)) for row in open_items), Decimal(0))
        nav = cash[account] + receivables - payables + dividends[account]
        nav -= short_dividends[account] + expenses[account]
        nav += values[account]
        result[account] = dict(cash=cash[account], market_value=values[account],
                               receivables=receivables, payables=payables,
                               dividend_receivable=dividends[account],
                               short_dividend_payable=short_dividends[account],
                               expense_payable=expenses[account], nav=nav)
    return dict(business_date=day, accounts=result, positions=positions,
                open_obligations=obligations,
                prior_execution_ids=sorted(prior_ids | set(trades)))
