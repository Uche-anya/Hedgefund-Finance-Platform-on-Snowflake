"""Account and position rows for exploring a provisional close."""

from collections import defaultdict
from decimal import Decimal

RATIO_SCALE = Decimal('0.00000001')


def number(value):
    amount = Decimal(value)
    if not amount.is_finite():
        raise ValueError('Non-finite amount in reporting input')
    return amount


def ratio(numerator, denominator):
    if denominator <= 0:
        raise ValueError('NAV denominator is not positive')
    return str((numerator / denominator).quantize(RATIO_SCALE))


def make_reporting_rows(daily, positions, instruments, scenario_id, ledger_id):
    """Return account-day and position-day rows without changing source data."""
    accounts = {}
    for row in daily:
        key = (row['business_date'], row['account_id'])
        if key in accounts or row['status'] != 'PROVISIONAL_UNAPPROVED':
            raise ValueError(f'Repeated or non-provisional account day: {key}')
        accounts[key] = row

    periods = defaultdict(list)
    for item in instruments:
        periods[item['security_id']].append(item)
    totals = defaultdict(lambda: {'long': Decimal(0), 'short': Decimal(0)})
    seen_positions = set()
    mapped_positions = []
    for row in positions:
        key = (row['business_date'], row['account_id'])
        grain = (*key, row['security_id'])
        if grain in seen_positions or key not in accounts:
            raise ValueError(f'Repeated position or missing account day: {grain}')
        seen_positions.add(grain)
        day = row['business_date']
        matches = [item for item in periods[row['security_id']]
                   if item['valid_from'] <= day <= item['valid_to']]
        if len(matches) != 1 or matches[0]['currency'] != 'USD':
            raise ValueError(f'No single dated security mapping: {grain}')
        quantity = number(row['quantity'])
        price = number(row['close_price_usd'])
        value = number(row['market_value_usd'])
        if quantity == 0 or price <= 0 or value != quantity * price:
            raise ValueError(f'Position value does not equal shares times price: {grain}')
        if value > 0:
            totals[key]['long'] += value
        else:
            totals[key]['short'] += -value
        mapped_positions.append((row, matches[0], value))

    account_rows = []
    for key, row in sorted(accounts.items()):
        long_value = totals[key]['long']
        short_value = totals[key]['short']
        gross = long_value + short_value
        net = long_value - short_value
        cash = number(row['settled_cash_usd'])
        trade_receivable = number(row['trade_receivable_usd'])
        trade_payable = number(row['trade_payable_usd'])
        reviewed_receivable = number(row['reviewed_dividend_receivable_usd'])
        reviewed_payable = number(row['reviewed_short_dividend_payable_usd'])
        reviewed_nav = number(row['nav_excluding_pending_actions_usd'])
        pending = number(row['pending_candidate_impact_usd'])
        illustrative = number(row['illustrative_nav_usd'])
        if (net != number(row['market_value_usd'])
                or cash + trade_receivable - trade_payable + net
                   != number(row['nav_before_dividends_usd'])
                or number(row['nav_before_dividends_usd'])
                   + reviewed_receivable - reviewed_payable != reviewed_nav
                or reviewed_nav + pending != illustrative):
            raise ValueError(f'Position or NAV totals do not match the close: {key}')
        account_rows.append({
            'scenario_id': scenario_id, 'ledger_id': ledger_id,
            'business_date': key[0], 'account_id': key[1], 'currency': 'USD',
            'nav_status': 'PROVISIONAL_UNAPPROVED',
            'reviewed_nav_usd': str(reviewed_nav),
            'illustrative_nav_usd': str(illustrative),
            'pending_candidate_impact_usd': str(pending),
            'settled_cash_usd': str(cash),
            'trade_receivable_usd': str(trade_receivable),
            'trade_payable_usd': str(trade_payable),
            'reviewed_dividend_receivable_usd': str(reviewed_receivable),
            'reviewed_short_dividend_payable_usd': str(reviewed_payable),
            'long_market_value_usd': str(long_value),
            'short_market_value_abs_usd': str(short_value),
            'net_market_value_usd': str(net),
            'gross_market_exposure_usd': str(gross),
            'gross_exposure_to_reviewed_nav_ratio': ratio(gross, reviewed_nav),
            'net_exposure_to_reviewed_nav_ratio': ratio(net, reviewed_nav),
        })

    position_rows = []
    for row, security, value in mapped_positions:
        key = (row['business_date'], row['account_id'])
        account_nav = number(accounts[key]['nav_excluding_pending_actions_usd'])
        gross = totals[key]['long'] + totals[key]['short']
        position_rows.append({
            'scenario_id': scenario_id, 'ledger_id': ledger_id,
            'business_date': key[0], 'account_id': key[1],
            'security_id': row['security_id'],
            'instrument_version_id': security['instrument_version_id'],
            'ticker_as_of_date': security['ticker'],
            'security_name_as_of_date': security['security_name'],
            'position_side': 'LONG' if value > 0 else 'SHORT',
            'quantity': row['quantity'],
            'close_price_usd': row['close_price_usd'],
            'market_value_usd': row['market_value_usd'],
            'signed_weight_to_reviewed_nav_ratio': ratio(value, account_nav),
            'absolute_weight_of_gross_exposure_ratio': ratio(abs(value), gross),
        })
    return account_rows, position_rows
