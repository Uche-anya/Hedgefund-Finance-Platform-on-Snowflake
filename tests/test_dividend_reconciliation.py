import unittest

from fund_pipeline.dividend_reconciliation import compare


class DividendReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.entitlement = dict(account_id='A', event_id='action-1',
                                pay_date='2025-02-07', opening_quantity='47',
                                cash_per_share_usd='0.76', gross_amount_usd='35.72',
                                review_status='APPROVED_IN_SEED')
        self.payment = dict(account_id='A', corporate_action_id='action-1',
                            settlement_date='2025-02-07', currency='USD',
                            instrument_id='MA.US', event_type='DIVIDEND_PAYMENT_CONFIRMED',
                            settled_at='2025-02-07T18:00:00+00:00',
                            published_at='2025-02-07T18:01:00+00:00',
                            source_system='simulated_custodian', is_simulated=True,
                            cash_amount='35.72')
        self.bank = dict(account_id='A', statement_date='2025-02-07',
                         currency='USD', source_system='simulated_bank',
                         is_simulated=True, closing_balance='1035.72')

    def test_matching_payment_clears_receivable_and_matches_bank(self):
        row = compare(self.entitlement, self.payment, self.bank, '1000.00')
        self.assertEqual(row['outstanding_usd'], '0.00')
        self.assertEqual(row['payment_status'], 'MATCHED')
        self.assertEqual(row['bank_status'], 'MATCHED')

    def test_short_payment_and_wrong_bank_balance_remain_visible(self):
        payment = {**self.payment, 'cash_amount': '30.00'}
        row = compare(self.entitlement, payment, self.bank, '1000.00')
        self.assertEqual(row['outstanding_usd'], '5.72')
        self.assertEqual(row['payment_status'], 'AMOUNT_MISMATCH')
        self.assertEqual(row['bank_difference_usd'], '5.72')
        self.assertEqual(row['bank_status'], 'BALANCE_MISMATCH')

    def test_missing_confirmation_does_not_create_cash(self):
        row = compare(self.entitlement, None, None, '1000.00')
        self.assertEqual(row['outstanding_usd'], '35.72')
        self.assertEqual(row['cash_after_payment_usd'], '1000.00')
        self.assertEqual(row['payment_status'], 'NO_CONFIRMATION')

    def test_wrong_instrument_cannot_clear_receivable(self):
        with self.assertRaisesRegex(ValueError, 'does not identify'):
            compare(self.entitlement, {**self.payment, 'instrument_id': 'V.US'},
                    self.bank, '1000.00')


if __name__ == '__main__':
    unittest.main()
