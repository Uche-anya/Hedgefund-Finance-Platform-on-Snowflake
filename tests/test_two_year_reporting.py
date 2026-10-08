import unittest

from fund_pipeline.two_year_reporting import make_reporting_rows


class ReportingRowsTests(unittest.TestCase):
    def setUp(self):
        self.daily = []
        for day, market_value, pending in (
                ('2026-05-19', '50', '0'),
                ('2026-05-20', '-12', '2')):
            reviewed_nav = str(100 + int(market_value))
            self.daily.append({
                'business_date': day, 'account_id': 'ACCOUNT-1',
                'status': 'PROVISIONAL_UNAPPROVED',
                'settled_cash_usd': '100', 'trade_receivable_usd': '0',
                'trade_payable_usd': '0', 'market_value_usd': market_value,
                'nav_before_dividends_usd': reviewed_nav,
                'reviewed_dividend_receivable_usd': '0',
                'reviewed_short_dividend_payable_usd': '0',
                'nav_excluding_pending_actions_usd': reviewed_nav,
                'pending_candidate_impact_usd': pending,
                'illustrative_nav_usd': str(int(reviewed_nav) + int(pending)),
            })
        self.positions = [
            {'business_date': '2026-05-19', 'account_id': 'ACCOUNT-1',
             'security_id': 'SEC', 'quantity': '10', 'close_price_usd': '5',
             'market_value_usd': '50'},
            {'business_date': '2026-05-20', 'account_id': 'ACCOUNT-1',
             'security_id': 'SEC', 'quantity': '-2', 'close_price_usd': '6',
             'market_value_usd': '-12'},
        ]
        self.instruments = [
            {'security_id': 'SEC', 'instrument_version_id': 'SEC_V1',
             'ticker': 'OLD', 'security_name': 'Fictional Co', 'currency': 'USD',
             'valid_from': '2026-05-19', 'valid_to': '2026-05-19'},
            {'security_id': 'SEC', 'instrument_version_id': 'SEC_V2',
             'ticker': 'NEW', 'security_name': 'Fictional Co', 'currency': 'USD',
             'valid_from': '2026-05-20', 'valid_to': '9999-12-31'},
        ]

    def test_position_values_and_dated_ticker(self):
        accounts, positions = make_reporting_rows(
            self.daily, self.positions, self.instruments, 'scenario', 'ledger')
        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts[0]['gross_market_exposure_usd'], '50')
        self.assertEqual(accounts[1]['short_market_value_abs_usd'], '12')
        self.assertEqual(accounts[1]['reviewed_nav_usd'], '88')
        self.assertEqual(accounts[1]['pending_candidate_impact_usd'], '2')
        self.assertEqual([row['ticker_as_of_date'] for row in positions],
                         ['OLD', 'NEW'])
        self.assertEqual(positions[1]['position_side'], 'SHORT')
        self.assertEqual(positions[1]['absolute_weight_of_gross_exposure_ratio'],
                         '1.00000000')

    def test_position_must_add_back_to_account_close(self):
        wrong = [dict(row) for row in self.positions]
        wrong[1]['market_value_usd'] = '-13'
        with self.assertRaisesRegex(ValueError, 'shares times price'):
            make_reporting_rows(self.daily, wrong, self.instruments,
                                'scenario', 'ledger')


if __name__ == '__main__':
    unittest.main()
