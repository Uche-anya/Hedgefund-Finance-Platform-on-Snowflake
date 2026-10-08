import copy
import unittest
from decimal import Decimal

from fund_pipeline.daily_continuation import calculate


class NextDayCloseTests(unittest.TestCase):
    def setUp(self):
        self.opening = {
            'opening_id': 'close-7', 'business_date': '2025-02-07',
            'cash': [{'account_id': 'FUND', 'reported_settled_cash': '1000',
                      'dividend_receivable': '5', 'short_dividend_payable': '2',
                      'expense_payable': '3'}],
            'positions': [{'account_id': 'FUND', 'security_id': 'APPLE',
                           'closing_quantity': '10'}],
            'obligations': [{'account_id': 'FUND', 'security_id': 'APPLE',
                             'execution_id': 'OLD', 'expected_cash': '20',
                             'settlement_due': '2025-02-07'}]
        }
        base = {'record_type': 'EXECUTION', 'business_date': '2025-02-10',
                'account_id': 'FUND', 'security_id': 'APPLE', 'execution_id': 'NEW',
                'side': 'BUY', 'execution_price': '11', 'settlement_due': '2025-02-11'}
        v1 = dict(base, event_id='v1', execution_version=1, quantity='1',
                  published_at='2025-02-10T16:00:00Z')
        v2 = dict(base, event_id='v2', execution_version=2, quantity='2',
                  supersedes_event_id='v1', published_at='2025-02-10T16:01:00Z')
        settlement = {'record_type': 'SETTLEMENT', 'event_id': 's1',
                      'business_date': '2025-02-10', 'account_id': 'FUND',
                      'execution_id': 'OLD', 'cash_amount': '20',
                      'settled_at': '2025-02-10T17:00:00Z',
                      'published_at': '2025-02-10T17:01:00Z'}
        self.delivery = {'opening_id': 'close-7', 'business_date': '2025-02-10',
                         'cutoff': '2025-02-11T08:00:00Z',
                         'events': [v1, v2, settlement]}

    def test_late_settlement_and_trade_correction(self):
        close = calculate(self.opening, self.delivery, {'APPLE': '12'})
        account = close['accounts']['FUND']
        self.assertEqual(close['positions'][('FUND', 'APPLE')], Decimal('12'))
        self.assertEqual(account['cash'], Decimal('1020'))
        self.assertEqual(account['receivables'], Decimal('0'))
        self.assertEqual(account['payables'], Decimal('22'))
        self.assertEqual(account['nav'], Decimal('1142'))
        self.assertEqual(close, calculate(self.opening, self.delivery, {'APPLE': '12'}))
        self.assertEqual(self.opening['cash'][0]['reported_settled_cash'], '1000')

    def test_duplicate_old_trade_cannot_enter_new_delivery(self):
        delivery = copy.deepcopy(self.delivery)
        delivery['events'][0]['execution_id'] = 'OLD'
        delivery['events'][1]['execution_id'] = 'OLD'
        with self.assertRaisesRegex(ValueError, 'reused execution ID'):
            calculate(self.opening, delivery, {'APPLE': '12'})

    def test_late_correction_after_cutoff_is_rejected(self):
        delivery = copy.deepcopy(self.delivery)
        delivery['events'][1]['published_at'] = '2025-02-11T09:00:00Z'
        with self.assertRaisesRegex(ValueError, 'after cutoff'):
            calculate(self.opening, delivery, {'APPLE': '12'})

    def test_unmatched_settlement_is_rejected(self):
        delivery = copy.deepcopy(self.delivery)
        delivery['events'][2]['cash_amount'] = '19'
        with self.assertRaisesRegex(ValueError, 'amount differs'):
            calculate(self.opening, delivery, {'APPLE': '12'})

    def test_missing_price_stops_close(self):
        with self.assertRaisesRegex(ValueError, 'Missing close price'):
            calculate(self.opening, self.delivery, {})


if __name__ == '__main__':
    unittest.main()
