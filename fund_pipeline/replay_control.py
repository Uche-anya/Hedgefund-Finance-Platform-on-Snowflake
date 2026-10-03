"""Independent Decimal calculations for checking the multi-day dbt results."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal


def calculate(records, prices, tickers, dividends=(), admin_events=()):
    sessions = sorted((r for r in records if r['record_type'] == 'SESSION'), key=lambda r: r['business_date'])
    openings = {r['account_id']: Decimal(r['amount']) for r in records if r['record_type'] == 'OPENING_CASH'}
    trades = [r for r in records if r['record_type'] == 'EXECUTION']
    settlements = {r['execution_id']: r for r in records if r['record_type'] == 'SETTLEMENT'}
    # Entitlements use trades strictly before the ex-date, then stay fixed.
    entitlements = []
    for dividend in dividends:
        for account in openings:
            shares = sum((Decimal(t['quantity']) * (1 if t['side'] == 'BUY' else -1)
                          for t in trades if t['account_id'] == account
                          and t['market_ticker'] == dividend['ticker']
                          and t['business_date'] < dividend['ex_date']), Decimal(0))
            entitlements.append((account, dividend['ex_date'], shares * Decimal(dividend['amount'])))
    payments = [r for r in records if r['record_type'] == 'DIVIDEND_PAYMENT']
    seen_payments = set()
    for payment in payments:
        key = (payment['account_id'], payment['corporate_action_id'])
        if key in seen_payments:
            raise ValueError('Duplicate dividend payment')
        seen_payments.add(key)
        dividend = next((d for d in dividends if d.get('event_id') == key[1]), None)
        if dividend is None or payment['account_id'] not in openings:
            raise ValueError('Dividend payment has no matching entitlement')
        amount = next(value for account, ex_date, value in entitlements
                      if account == key[0] and ex_date == dividend['ex_date'])
        settled = datetime.fromisoformat(payment['settled_at'])
        published = datetime.fromisoformat(payment['published_at'])
        if (Decimal(payment['cash_amount']) != amount or amount == 0
                or payment['currency'] != 'USD'
                or payment['instrument_id'] != dividend['ticker'] + '.US'
                or published < settled or settled.date().isoformat() < dividend['ex_date']):
            raise ValueError('Dividend payment does not match the reviewed entitlement')
    holdings = defaultdict(Decimal)
    valuations, balances = {}, {}
    for session in sessions:
        day = session['business_date']
        cutoff = datetime.fromisoformat(session['cutoff'])
        opening_positions = holdings.copy()
        for trade in trades:
            if trade['business_date'] == day:
                key = (trade['account_id'], trade['market_ticker'])
                holdings[key] += Decimal(trade['quantity']) * (1 if trade['side'] == 'BUY' else -1)
        for account, opening_cash in openings.items():
            net_value = Decimal(0)
            gross = Decimal(0)
            for ticker in tickers:
                quantity = holdings[(account, ticker)]
                previous = opening_positions.get((account, ticker), Decimal(0))
                price = prices[(day, ticker)]
                value = quantity * price
                valuations[(day, account, ticker + '.US')] = {
                    'opening_quantity': previous, 'net_trade_quantity': quantity - previous,
                    'closing_quantity': quantity, 'close_price': price, 'market_value': value}
                net_value += value
                gross += abs(value)
            cash, trade_cash = opening_cash, opening_cash
            receivables, payables = Decimal(0), Decimal(0)
            for trade in trades:
                if trade['account_id'] != account or trade['business_date'] > day:
                    continue
                amount = Decimal(trade['quantity']) * Decimal(trade['execution_price'])
                amount *= -1 if trade['side'] == 'BUY' else 1
                trade_cash += amount
                settlement = settlements.get(trade['execution_id'])
                if (settlement is not None and datetime.fromisoformat(settlement['published_at']) <= cutoff
                        and datetime.fromisoformat(settlement['settled_at']) <= cutoff):
                    cash += Decimal(settlement['cash_amount'])
                elif amount > 0:
                    receivables += amount
                else:
                    payables -= amount
            dividend_receivable = sum((max(amount, Decimal(0))
                                       for owner, ex_date, amount in entitlements
                                       if owner == account and ex_date <= day), Decimal(0))
            short_dividend_payable = sum((max(-amount, Decimal(0))
                                         for owner, ex_date, amount in entitlements
                                         if owner == account and ex_date <= day), Decimal(0))
            confirmed_dividend_cash = Decimal(0)
            for payment in payments:
                if (payment['account_id'] == account
                        and datetime.fromisoformat(payment['settled_at']) <= cutoff
                        and datetime.fromisoformat(payment['published_at']) <= cutoff):
                    amount = Decimal(payment['cash_amount'])
                    confirmed_dividend_cash += amount
                    dividend_receivable -= max(amount, Decimal(0))
                    short_dividend_payable -= max(-amount, Decimal(0))
            cash += confirmed_dividend_cash
            investor_flows = sum((Decimal(event['amount']) for event in admin_events
                                  if event['account_id'] == account
                                  and event['event_type'].startswith('INVESTOR_')
                                  and event['event_date'] <= day), Decimal(0))
            accrued_expenses = sum((Decimal(event['amount']) for event in admin_events
                                    if event['account_id'] == account
                                    and event['event_type'] == 'EXPENSE'
                                    and event['event_date'] <= day), Decimal(0))
            paid_expenses = sum((Decimal(event['amount']) for event in admin_events
                                 if event['account_id'] == account
                                 and event['event_type'] == 'EXPENSE'
                                 and event['payment_date'] <= day), Decimal(0))
            expense_payable = accrued_expenses - paid_expenses
            cash += investor_flows - paid_expenses
            accrual_basis_cash = trade_cash + investor_flows - accrued_expenses
            nav_before_dividends = accrual_basis_cash + net_value
            balances[(day, account)] = {
                'reported_settled_cash': cash, 'receivables': receivables, 'payables': payables,
                'trade_date_cash': trade_cash, 'net_market_value': net_value, 'gross_exposure': gross,
                'confirmed_dividend_cash': confirmed_dividend_cash,
                'dividend_receivable': dividend_receivable, 'short_dividend_payable': short_dividend_payable,
                'investor_flows': investor_flows, 'paid_expenses': paid_expenses,
                'expense_payable': expense_payable, 'accrual_basis_cash': accrual_basis_cash,
                'nav_before_dividends': nav_before_dividends,
                'simplified_nav': nav_before_dividends + confirmed_dividend_cash + dividend_receivable - short_dividend_payable}
    return valuations, balances
