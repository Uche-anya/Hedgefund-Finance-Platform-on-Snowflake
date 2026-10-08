"""An illustrative daily equity ledger with optional confirmed dividend cash."""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite():
        raise ValueError('Non-finite amount')
    return amount


def calculate(sessions, opening_cash, prices, identities, trades, settlements,
              dividends, transfers, payments=None, show_review_split=False):
    payments = payments or {}
    cash = {account: money(amount) for account, amount in opening_cash.items()}
    positions = defaultdict(Decimal)
    dividend_receivable = defaultdict(Decimal)
    short_dividend_payable = defaultdict(Decimal)
    pending_receivable = defaultdict(Decimal)
    pending_payable = defaultdict(Decimal)
    pending_dividend_net = defaultdict(Decimal)
    dividend_by_event = {}
    entitlement_rows = {}
    obligations = {}
    seen_executions = set()
    seen_payments = set()
    daily = []
    position_rows = []
    entitlements = []
    transfers_done = []

    for day in sessions:
        cutoff = datetime.fromisoformat(day + 'T23:00:00+00:00')
        for transfer in transfers.get(day, []):
            old, new = transfer['predecessor_security_id'], transfer['security_id']
            if old == new or transfer['ratio'] != '1':
                raise ValueError(f'Unsupported security transfer on {day}')
            for account in cash:
                quantity = positions.pop((account, old), Decimal(0))
                positions[(account, new)] += quantity
                transfers_done.append(dict(business_date=day, account_id=account,
                                           from_security_id=old, to_security_id=new,
                                           quantity=str(quantity)))

        # Ex-date entitlement uses yesterday's closing shares, before today's fills.
        for action in dividends.get(day, []):
            security = action['security_id']
            rate = money(action['cash_amount'])
            if (rate <= 0 or action['currency'] != 'USD'
                    or action['review_status'] not in ('APPROVED_IN_SEED', 'PENDING')):
                raise ValueError(f'Invalid dividend: {action["event_id"]}')
            for account in cash:
                quantity = positions[(account, security)]
                amount = quantity * rate
                dividend_receivable[account] += max(amount, 0)
                short_dividend_payable[account] += max(-amount, 0)
                if action['review_status'] == 'PENDING':
                    pending_dividend_net[account] += amount
                    pending_receivable[account] += max(amount, 0)
                    pending_payable[account] += max(-amount, 0)
                key = (account, action['event_id'])
                if key in dividend_by_event:
                    raise ValueError(f'Repeated dividend entitlement: {key}')
                dividend_by_event[key] = {
                    'remaining': amount, 'pay_date': action['pay_date'],
                    'instrument_id': action.get('ticker', '') + '.US',
                    'review_status': action['review_status'],
                }
                row = dict(event_id=action['event_id'], account_id=account,
                                         security_id=security, ex_dividend_date=day,
                                         pay_date=action['pay_date'],
                                         opening_quantity=str(quantity),
                                         cash_per_share_usd=str(rate),
                                         gross_amount_usd=str(amount),
                                         review_status=action['review_status'],
                                         payment_status='NO_CONFIRMATION')
                entitlements.append(row)
                entitlement_rows[key] = row

        for trade in trades.get(day, []):
            execution_id = trade['execution_id']
            executed = datetime.fromisoformat(trade['executed_at'].replace('Z', '+00:00'))
            published = datetime.fromisoformat(trade['published_at'].replace('Z', '+00:00'))
            if (execution_id in seen_executions or trade['execution_status'] != 'ACTIVE'
                    or trade['execution_version'] != 1 or trade['business_date'] != day
                    or trade['event_type'] != 'EXECUTION_REPORTED'
                    or trade['source_system'] != 'simulated_oms'
                    or trade['is_simulated'] is not True
                    or executed.date().isoformat() != day
                    or not executed <= published <= cutoff):
                raise ValueError(f'Unsupported or repeated execution: {execution_id}')
            seen_executions.add(execution_id)
            account = trade['account_id']
            if account not in cash or trade['currency'] != 'USD':
                raise ValueError(f'Unknown account or currency: {execution_id}')
            security = identities[(day, trade['market_ticker'])]
            quantity = money(trade['quantity'])
            price = money(trade['execution_price'])
            if quantity <= 0 or price <= 0 or trade['side'] not in ('BUY', 'SELL'):
                raise ValueError(f'Invalid execution: {execution_id}')
            sign = 1 if trade['side'] == 'BUY' else -1
            positions[(account, security)] += sign * quantity
            obligations[execution_id] = {
                'account_id': account, 'instrument_id': trade['instrument_id'],
                'side': trade['side'], 'quantity': quantity,
                'settlement_due': trade['settlement_due'],
                'expected_cash': -sign * quantity * price,
            }

        due = {execution_id for execution_id, item in obligations.items()
               if item['settlement_due'] == day}
        received = settlements.get(day, [])
        received_ids = {row['execution_id'] for row in received}
        if len(received_ids) != len(received) or received_ids != due:
            raise ValueError(f'Settlements differ from trades due on {day}')
        for row in received:
            execution_id = row['execution_id']
            item = obligations[execution_id]
            settled_at = datetime.fromisoformat(row['settled_at'].replace('Z', '+00:00'))
            published_at = datetime.fromisoformat(row['published_at'].replace('Z', '+00:00'))
            if (row['account_id'] != item['account_id']
                    or row['instrument_id'] != item['instrument_id']
                    or row['side'] != item['side']
                    or money(row['settled_quantity']) != item['quantity']
                    or money(row['cash_amount']) != item['expected_cash']
                    or row['settlement_date'] != day
                    or row['settlement_status'] != 'SETTLED'
                    or row['event_type'] != 'SETTLEMENT_CONFIRMED'
                    or row['source_system'] != 'simulated_custodian'
                    or row['is_simulated'] is not True
                    or settled_at.date().isoformat() != day
                    or not settled_at <= published_at <= cutoff):
                raise ValueError(f'Mismatched settlement: {execution_id}')
            cash[item['account_id']] += item['expected_cash']
            del obligations[execution_id]

        for payment in payments.get(day, []):
            payment_id = payment['event_id']
            key = (payment['account_id'], payment['corporate_action_id'])
            item = dividend_by_event.get(key)
            settled_at = datetime.fromisoformat(payment['settled_at'].replace('Z', '+00:00'))
            published_at = datetime.fromisoformat(payment['published_at'].replace('Z', '+00:00'))
            if (payment_id in seen_payments or item is None
                    or item['review_status'] != 'APPROVED_IN_SEED'
                    or day < item['pay_date']
                    or payment['settlement_date'] != day
                    or payment['instrument_id'] != item['instrument_id']
                    or payment['currency'] != 'USD'
                    or payment['event_type'] != 'DIVIDEND_PAYMENT_CONFIRMED'
                    or payment['source_system'] != 'simulated_custodian'
                    or payment['is_simulated'] is not True
                    or settled_at.date().isoformat() != day
                    or not settled_at <= published_at <= cutoff):
                raise ValueError(f'Unsupported dividend payment: {payment_id}')
            amount = money(payment['cash_amount'])
            remaining = item['remaining']
            if (remaining == 0 or amount == 0 or amount * remaining <= 0
                    or abs(amount) > abs(remaining)):
                raise ValueError(f'Dividend payment exceeds entitlement: {payment_id}')
            seen_payments.add(payment_id)
            item['remaining'] -= amount
            cash[key[0]] += amount
            if amount > 0:
                dividend_receivable[key[0]] -= amount
            else:
                short_dividend_payable[key[0]] += amount
            entitlement_rows[key]['payment_status'] = (
                'MATCHED' if item['remaining'] == 0 else 'PARTIAL')

        for account in cash:
            market_value = Decimal(0)
            for (owner, security), quantity in sorted(positions.items()):
                if owner != account or quantity == 0:
                    continue
                if security not in prices[day]:
                    raise ValueError(f'Missing {day} close for {security}')
                value = quantity * money(prices[day][security])
                market_value += value
                position_rows.append(dict(business_date=day, account_id=account,
                                          security_id=security, quantity=str(quantity),
                                          close_price_usd=str(prices[day][security]),
                                          market_value_usd=str(value)))
            open_items = [item['expected_cash'] for item in obligations.values()
                          if item['account_id'] == account]
            receivable = sum((max(amount, 0) for amount in open_items), Decimal(0))
            payable = sum((max(-amount, 0) for amount in open_items), Decimal(0))
            before_dividends = cash[account] + receivable - payable + market_value
            illustrative_nav = (before_dividends + dividend_receivable[account]
                                - short_dividend_payable[account])
            row = dict(business_date=day, account_id=account,
                              settled_cash_usd=str(cash[account]),
                              market_value_usd=str(market_value),
                              trade_receivable_usd=str(receivable),
                              trade_payable_usd=str(payable),
                              dividend_receivable_unconfirmed_usd=str(dividend_receivable[account]),
                              short_dividend_payable_unconfirmed_usd=str(short_dividend_payable[account]),
                              pending_review_dividend_net_usd=str(pending_dividend_net[account]),
                              nav_before_dividends_usd=str(before_dividends),
                              illustrative_nav_usd=str(illustrative_nav),
                              status='PROVISIONAL_UNAPPROVED')
            if show_review_split:
                reviewed_receivable = dividend_receivable[account] - pending_receivable[account]
                reviewed_payable = short_dividend_payable[account] - pending_payable[account]
                pending_impact = pending_receivable[account] - pending_payable[account]
                if (reviewed_receivable < 0 or reviewed_payable < 0
                        or pending_impact != pending_dividend_net[account]):
                    raise ValueError(f'Dividend review balances do not reconcile: {account}/{day}')
                row.update(
                    reviewed_dividend_receivable_usd=str(reviewed_receivable),
                    reviewed_short_dividend_payable_usd=str(reviewed_payable),
                    pending_dividend_receivable_usd=str(pending_receivable[account]),
                    pending_short_dividend_payable_usd=str(pending_payable[account]),
                    pending_candidate_impact_usd=str(pending_impact),
                    nav_excluding_pending_actions_usd=str(
                        before_dividends + reviewed_receivable - reviewed_payable),
                )
            daily.append(row)
    if obligations:
        raise ValueError(f'{len(obligations)} trades remain unsettled at the last close')
    if len(seen_payments) != sum(map(len, payments.values())):
        raise ValueError('Payment date is outside the close calendar')
    return daily, position_rows, entitlements, transfers_done
