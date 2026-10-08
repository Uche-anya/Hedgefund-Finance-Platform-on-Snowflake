from decimal import Decimal
import unittest

from scripts.prepare_two_year_action_review_queue import ranked_row


class ReviewQueueTests(unittest.TestCase):
    def test_opposing_accounts_do_not_cancel_review_priority(self):
        action = {
            'event_id': 'd1', 'ticker': 'TEST', 'security_id': 's1',
            'ex_dividend_date': '2026-05-19', 'record_date': '2026-05-19',
            'pay_date': '2026-06-10', 'cash_per_share_usd': '2',
            'distribution_type': 'recurring', 'identity_status': 'review',
            'source_file': 'source.json', 'source_row_number': '1',
            'review_status': 'PENDING',
        }
        first = {
            'account_id': 'SIM-REPLAY-01', 'event_id': 'd1', 'security_id': 's1',
            'ex_dividend_date': '2026-05-19', 'pay_date': '2026-06-10',
            'review_status': 'PENDING', 'payment_status': 'NO_CONFIRMATION',
            'cash_per_share_usd': '2', 'opening_quantity': '-50',
            'gross_amount_usd': '-100',
        }
        second = dict(first, account_id='SIM-REPLAY-02',
                      opening_quantity='50', gross_amount_usd='100')

        row = ranked_row(action, [first, second])

        self.assertEqual(Decimal(row['net_candidate_impact_usd']), Decimal('0'))
        self.assertEqual(Decimal(row['gross_absolute_exposure_usd']), Decimal('200'))
        self.assertEqual(Decimal(row['possible_short_payments_usd']), Decimal('100'))
        self.assertEqual(Decimal(row['possible_long_receipts_usd']), Decimal('100'))


if __name__ == '__main__':
    unittest.main()
