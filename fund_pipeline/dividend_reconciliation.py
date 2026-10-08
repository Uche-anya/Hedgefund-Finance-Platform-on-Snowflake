"""Compare a dividend accrual with custodian cash and a bank closing balance."""

from decimal import Decimal
from datetime import datetime


def compare(entitlement, payment, bank, settled_cash):
    account = entitlement['account_id']
    expected = Decimal(entitlement['gross_amount_usd'])
    if entitlement['review_status'] != 'APPROVED_IN_SEED' or expected <= 0:
        raise ValueError('Pilot requires a reviewed positive dividend entitlement')
    if expected != expected.quantize(Decimal('0.01')):
        raise ValueError('Entitlement has fractions of a cent')
    if payment is not None and (payment['account_id'] != account
                                or payment['corporate_action_id'] != entitlement['event_id']
                                or payment['settlement_date'] != entitlement['pay_date']
                                or payment['currency'] != 'USD'
                                or payment['instrument_id'] != 'MA.US'
                                or payment['event_type'] != 'DIVIDEND_PAYMENT_CONFIRMED'
                                or payment['source_system'] != 'simulated_custodian'
                                or payment['is_simulated'] is not True):
        raise ValueError('Custodian confirmation does not identify this entitlement')
    if bank is not None and (bank['account_id'] != account
                             or bank['statement_date'] != entitlement['pay_date']
                             or bank['currency'] != 'USD'
                             or bank['source_system'] != 'simulated_bank'
                             or bank['is_simulated'] is not True):
        raise ValueError('Bank statement has the wrong account or date')
    if payment is not None:
        settled = datetime.fromisoformat(payment['settled_at'])
        published = datetime.fromisoformat(payment['published_at'])
        if settled.date().isoformat() != entitlement['pay_date'] or published < settled:
            raise ValueError('Custodian payment timing is invalid')
    paid = Decimal(payment['cash_amount']) if payment else Decimal(0)
    if paid < 0 or paid != paid.quantize(Decimal('0.01')):
        raise ValueError('Invalid payment amount')
    expected = expected.quantize(Decimal('0.01'))
    paid = paid.quantize(Decimal('0.01'))
    baseline = Decimal(settled_cash)
    bank_balance = Decimal(bank['closing_balance']) if bank else None
    outstanding = expected - paid
    expected_bank = baseline + paid
    return {
        'account_id': account, 'corporate_action_id': entitlement['event_id'],
        'opening_shares': entitlement['opening_quantity'],
        'cash_per_share_usd': entitlement['cash_per_share_usd'],
        'expected_usd': str(expected), 'confirmed_usd': str(paid),
        'outstanding_usd': str(outstanding),
        'cash_before_payment_usd': str(baseline),
        'cash_after_payment_usd': str(expected_bank),
        'bank_reported_usd': str(bank_balance) if bank else None,
        'bank_difference_usd': str(bank_balance - expected_bank) if bank else None,
        'payment_status': ('NO_CONFIRMATION' if payment is None else
                           'MATCHED' if outstanding == 0 else 'AMOUNT_MISMATCH'),
        'bank_status': ('NO_STATEMENT' if bank is None else
                        'MATCHED' if bank_balance == expected_bank else 'BALANCE_MISMATCH'),
    }
