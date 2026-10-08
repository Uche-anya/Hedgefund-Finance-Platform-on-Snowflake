import unittest

from scripts.prepare_top_dividend_reviews import make_review


class TopDividendReviewTests(unittest.TestCase):
    def setUp(self):
        self.queue = {
            'event_id': 'event-1', 'ticker': 'PEP', 'record_date': '2025-12-05',
            'ex_dividend_date': '2025-12-05', 'pay_date': '2026-01-06',
            'cash_per_share_usd': '1.4225', 'review_status': 'PENDING',
            'account_01_opening_shares': '10',
            'account_01_signed_amount_usd': '14.225',
            'account_02_opening_shares': '-5',
            'account_02_signed_amount_usd': '-7.1125',
            'gross_absolute_exposure_usd': '21.3375',
        }
        self.triage = {
            'event_id': 'event-1', 'ticker': 'PEP', 'record_date': '2025-12-05',
            'ex_dividend_date': '2025-12-05', 'pay_date': '2026-01-06',
            'review_decision': 'PENDING', 'issuer_check': 'PARTIAL_ISSUER_MATCH',
            'conflicting_fields': '', 'issuer_source_url': 'https://issuer.example',
        }

    def test_matching_other_venue_notice_does_not_approve(self):
        notice = {'venue': 'XFRA', 'ex_dividend_date': '2025-12-05',
                  'source_url': 'https://exchange.example'}
        review = make_review(self.queue, self.triage, notice)
        self.assertEqual(review['recommendation'], 'AWAITING_REVIEW')
        self.assertEqual(review['approved'], 'NO')
        self.assertEqual(review['other_venue_ex_date'], '2025-12-05')

    def test_conflicting_exchange_notice_is_rejected(self):
        notice = {'venue': 'XFRA', 'ex_dividend_date': '2025-12-04',
                  'source_url': 'https://exchange.example'}
        with self.assertRaisesRegex(ValueError, 'Exchange notice differs'):
            make_review(self.queue, self.triage, notice)


if __name__ == '__main__':
    unittest.main()
