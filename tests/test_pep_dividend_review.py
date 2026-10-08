import unittest

from scripts.prepare_pep_dividend_review import prior_holdings


class PepsiCoReviewTests(unittest.TestCase):
    def test_prior_close_must_equal_dividend_opening(self):
        event = {'security_id': 'NB_EQ_0019', 'cash_per_share_usd': '1.4225'}
        positions = [
            {'business_date': '2025-12-04', 'account_id': 'SIM-REPLAY-01',
             'security_id': 'NB_EQ_0019', 'quantity': '-802',
             'close_price_usd': '146.91'},
            {'business_date': '2025-12-04', 'account_id': 'SIM-REPLAY-02',
             'security_id': 'NB_EQ_0019', 'quantity': '2946',
             'close_price_usd': '146.91'},
        ]
        entitlements = [
            {'account_id': 'SIM-REPLAY-01', 'opening_quantity': '-802',
             'gross_amount_usd': '-1140.845', 'payment_status': 'NO_CONFIRMATION'},
            {'account_id': 'SIM-REPLAY-02', 'opening_quantity': '2946',
             'gross_amount_usd': '4190.685', 'payment_status': 'NO_CONFIRMATION'},
        ]
        self.assertEqual(prior_holdings(positions, event, entitlements),
                         {'SIM-REPLAY-01': '-802', 'SIM-REPLAY-02': '2946'})
        entitlements[1]['opening_quantity'] = '2945'
        with self.assertRaisesRegex(ValueError, 'disagree'):
            prior_holdings(positions, event, entitlements)


if __name__ == '__main__':
    unittest.main()
