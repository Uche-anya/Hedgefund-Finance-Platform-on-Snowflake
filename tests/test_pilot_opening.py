import copy
import unittest

from scripts.close_daily_pilot import opening_from_statements


class PilotOpeningTests(unittest.TestCase):
    def setUp(self):
        self.admin = [{
            'record_id': 'a1', 'scenario_id': 'test',
            'source_system': 'simulated_fund_administrator',
            'is_simulated': True, 'event_type': 'INVESTOR_SUBSCRIPTION',
            'event_date': '2024-09-23', 'account_id': 'FUND',
            'currency': 'USD', 'amount': '5000000.00'}]
        self.bank = [{
            'record_id': 'b1', 'scenario_id': 'test',
            'source_system': 'simulated_bank', 'is_simulated': True,
            'statement_date': '2024-09-23', 'account_id': 'FUND',
            'currency': 'USD', 'closing_balance': '5000000.00',
            'published_at': '2024-09-23T23:00:00+00:00'}]

    def test_bank_and_admin_must_agree_before_first_close(self):
        opening = opening_from_statements('2024-09-23', 'test', ['FUND'],
                                          self.admin, self.bank,
                                          {'fund_admin': 'admin-1', 'bank_cash': 'bank-1'})
        self.assertEqual(opening['cash'][0]['reported_settled_cash'], '5000000.00')
        changed = copy.deepcopy(self.bank)
        changed[0]['closing_balance'] = '4999999.00'
        with self.assertRaisesRegex(ValueError, 'differ'):
            opening_from_statements('2024-09-23', 'test', ['FUND'], self.admin, changed, {})

    def test_duplicate_bank_account_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'cover every account once'):
            opening_from_statements('2024-09-23', 'test', ['FUND'],
                                    self.admin, self.bank + self.bank, {})


if __name__ == '__main__':
    unittest.main()
