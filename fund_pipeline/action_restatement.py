"""Move one reviewed dividend from pending to reviewed NAV."""

from decimal import Decimal


def reclassify_close(daily, entitlements, event, amounts):
    """Return a new close; leave the saved input rows alone."""
    ex_date = event['ex_dividend_date']
    changed_daily = []
    differences = []
    seen = set()

    for old in daily:
        key = (old['business_date'], old['account_id'])
        if key in seen or old['account_id'] not in amounts:
            raise ValueError('Repeated or unknown account-day close')
        seen.add(key)
        row = dict(old)
        if old['business_date'] >= ex_date:
            amount = Decimal(amounts[old['account_id']])
            receipt = max(amount, Decimal(0))
            payment = max(-amount, Decimal(0))

            def move(pending_column, reviewed_column, value):
                pending = Decimal(old[pending_column]) - value
                reviewed = Decimal(old[reviewed_column]) + value
                if pending < 0:
                    raise ValueError(f'Pending balance cannot cover the event: {key}')
                row[pending_column] = str(pending)
                row[reviewed_column] = str(reviewed)

            move('pending_dividend_receivable_usd',
                 'reviewed_dividend_receivable_usd', receipt)
            move('pending_short_dividend_payable_usd',
                 'reviewed_short_dividend_payable_usd', payment)
            row['pending_candidate_impact_usd'] = str(
                Decimal(old['pending_candidate_impact_usd']) - amount)
            row['pending_review_dividend_net_usd'] = str(
                Decimal(old['pending_review_dividend_net_usd']) - amount)
            row['nav_excluding_pending_actions_usd'] = str(
                Decimal(old['nav_excluding_pending_actions_usd']) + amount)

            if (Decimal(row['nav_excluding_pending_actions_usd'])
                    + Decimal(row['pending_candidate_impact_usd'])
                    != Decimal(old['illustrative_nav_usd'])
                    or Decimal(row['reviewed_dividend_receivable_usd'])
                    + Decimal(row['pending_dividend_receivable_usd'])
                    != Decimal(old['dividend_receivable_unconfirmed_usd'])
                    or Decimal(row['reviewed_short_dividend_payable_usd'])
                    + Decimal(row['pending_short_dividend_payable_usd'])
                    != Decimal(old['short_dividend_payable_unconfirmed_usd'])):
                raise ValueError(f'Reviewed and pending balances do not add up: {key}')
            differences.append({
                'business_date': key[0], 'account_id': key[1],
                'reviewed_nav_before_usd': old['nav_excluding_pending_actions_usd'],
                'reviewed_nav_after_usd': row['nav_excluding_pending_actions_usd'],
                'change_usd': str(amount),
            })
        changed_daily.append(row)

    changed_entitlements = []
    matched = set()
    for old in entitlements:
        row = dict(old)
        if old['event_id'] == event['event_id']:
            account = old['account_id']
            if (account in matched or account not in amounts
                    or old['review_status'] != 'PENDING'
                    or old['payment_status'] != 'NO_CONFIRMATION'
                    or Decimal(old['gross_amount_usd']) != Decimal(amounts[account])):
                raise ValueError('Entitlement differs from the approved decision')
            matched.add(account)
            row['review_status'] = 'APPROVED_BY_DECISION'
        changed_entitlements.append(row)
    if matched != set(amounts) or not differences or len(seen) != len(daily):
        raise ValueError('Approval did not cover the expected close and entitlement rows')
    return changed_daily, changed_entitlements, differences


def apply_ledger(daily, entitlements, entries):
    """Apply one decision per event to the same saved starting close."""
    decisions = {}
    ids = set()
    for decision, event, amounts in entries:
        event_id = event['event_id']
        decision_id = decision['decision_id']
        if (event_id in decisions or decision_id in ids
                or decision['event_id'] != event_id
                or decision['decision'] not in ('HOLD', 'APPROVE')):
            raise ValueError('Repeated or conflicting action decision')
        decisions[event_id] = (decision, event, amounts)
        ids.add(decision_id)

    new_daily = [dict(row) for row in daily]
    new_entitlements = [dict(row) for row in entitlements]
    affected = {}
    approved = []
    held = []
    for event_id in sorted(decisions):
        decision, event, amounts = decisions[event_id]
        if decision['decision'] == 'HOLD':
            held.append(event_id)
            continue
        new_daily, new_entitlements, differences = reclassify_close(
            new_daily, new_entitlements, event, amounts)
        approved.append(event_id)
        for row in differences:
            key = (row['business_date'], row['account_id'])
            affected.setdefault(key, []).append(event_id)

    report = []
    for before, after in zip(daily, new_daily):
        key = (before['business_date'], before['account_id'])
        if key != (after['business_date'], after['account_id']):
            raise ValueError('Close row order changed')
        if (before['illustrative_nav_usd'] != after['illustrative_nav_usd']
                or before['settled_cash_usd'] != after['settled_cash_usd']
                or Decimal(after['nav_excluding_pending_actions_usd'])
                   + Decimal(after['pending_candidate_impact_usd'])
                   != Decimal(after['illustrative_nav_usd'])):
            raise ValueError('Decision ledger changed the economic close')
        if key in affected:
            report.append({
                'business_date': key[0], 'account_id': key[1],
                'approved_event_ids': '|'.join(affected[key]),
                'reviewed_nav_before_usd': before['nav_excluding_pending_actions_usd'],
                'reviewed_nav_after_usd': after['nav_excluding_pending_actions_usd'],
                'change_usd': str(Decimal(after['nav_excluding_pending_actions_usd'])
                                  - Decimal(before['nav_excluding_pending_actions_usd'])),
            })
    if len(report) != len(affected):
        raise ValueError('Decision ledger changed the close grain')
    return new_daily, new_entitlements, report, approved, held
