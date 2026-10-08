import copy
from decimal import Decimal
import unittest

from fund_pipeline.two_year_close import calculate


class LongCloseTests(unittest.TestCase):
    def setUp(self):
        self.sessions = ['2026-07-01', '2026-07-02', '2026-07-03']
        self.prices = {'2026-07-01': {'OLD': '10'},
                       '2026-07-02': {'NEW': '11'},
                       '2026-07-03': {'NEW': '12'}}
        self.identities = {('2026-07-01', 'XOM'): 'OLD'}
        self.trades = {'2026-07-01': [{
            'execution_id': 'e1', 'execution_status': 'ACTIVE', 'execution_version': 1,
            'business_date': '2026-07-01', 'event_type': 'EXECUTION_REPORTED',
            'source_system': 'simulated_oms', 'is_simulated': True,
            'executed_at': '2026-07-01T15:00:00+00:00',
            'published_at': '2026-07-01T15:00:01+00:00',
            'account_id': 'FUND', 'currency': 'USD', 'market_ticker': 'XOM',
            'instrument_id': 'XOM.US', 'quantity': '2', 'execution_price': '10',
            'side': 'BUY', 'settlement_due': '2026-07-02'}]}
        self.settlements = {'2026-07-02': [{
            'execution_id': 'e1', 'account_id': 'FUND', 'instrument_id': 'XOM.US',
            'side': 'BUY', 'settled_quantity': '2', 'cash_amount': '-20',
            'settlement_date': '2026-07-02', 'settlement_status': 'SETTLED',
            'event_type': 'SETTLEMENT_CONFIRMED',
            'source_system': 'simulated_custodian', 'is_simulated': True,
            'settled_at': '2026-07-02T18:00:00+00:00',
            'published_at': '2026-07-02T18:00:30+00:00'}]}
        self.dividends = {'2026-07-02': [{
            'event_id': 'd1', 'security_id': 'NEW', 'cash_amount': '1',
            'currency': 'USD', 'pay_date': '2026-07-10',
            'review_status': 'PENDING'}]}
        self.transfers = {'2026-07-02': [{
            'predecessor_security_id': 'OLD', 'security_id': 'NEW', 'ratio': '1'}]}

    def test_transfer_and_ex_date_use_opening_shares(self):
        daily, positions, entitlements, moved = calculate(
            self.sessions, {'FUND': '1000'}, self.prices, self.identities,
            self.trades, self.settlements, self.dividends, self.transfers)
        self.assertEqual([row['illustrative_nav_usd'] for row in daily],
                         ['1000', '1004', '1006'])
        self.assertEqual(daily[1]['settled_cash_usd'], '980')
        self.assertEqual(daily[1]['dividend_receivable_unconfirmed_usd'], '2')
        self.assertEqual(entitlements[0]['opening_quantity'], '2')
        self.assertEqual(entitlements[0]['payment_status'], 'NO_CONFIRMATION')
        self.assertEqual(moved[0]['quantity'], '2')
        self.assertEqual(positions[-1]['security_id'], 'NEW')

    def test_missing_custodian_confirmation_stops_close(self):
        with self.assertRaisesRegex(ValueError, 'Settlements differ'):
            calculate(self.sessions, {'FUND': '1000'}, self.prices,
                      self.identities, self.trades, {}, self.dividends,
                      self.transfers)

    def test_purchase_on_ex_date_does_not_earn_dividend(self):
        action = dict(self.dividends['2026-07-02'][0], security_id='OLD')
        _, _, entitlements, _ = calculate(
            self.sessions, {'FUND': '1000'}, self.prices, self.identities,
            self.trades, self.settlements, {'2026-07-01': [action]}, self.transfers)
        self.assertEqual(entitlements[0]['opening_quantity'], '0')
        self.assertEqual(entitlements[0]['gross_amount_usd'], '0')

    def test_late_trade_is_not_used_for_that_close(self):
        trades = copy.deepcopy(self.trades)
        trades['2026-07-01'][0]['published_at'] = '2026-07-02T00:01:00+00:00'
        with self.assertRaisesRegex(ValueError, 'Unsupported or repeated execution'):
            calculate(self.sessions, {'FUND': '1000'}, self.prices,
                      self.identities, trades, self.settlements,
                      self.dividends, self.transfers)

    def test_confirmed_dividend_moves_receivable_into_cash_without_changing_nav(self):
        action = dict(self.dividends['2026-07-02'][0], ticker='XOM',
                      pay_date='2026-07-03', review_status='APPROVED_IN_SEED')
        payment = dict(event_id='p1', account_id='FUND', corporate_action_id='d1',
                       instrument_id='XOM.US', currency='USD', cash_amount='2',
                       settlement_date='2026-07-03',
                       settled_at='2026-07-03T18:00:00+00:00',
                       published_at='2026-07-03T18:01:00+00:00',
                       event_type='DIVIDEND_PAYMENT_CONFIRMED',
                       source_system='simulated_custodian', is_simulated=True)
        daily, _, entitlements, _ = calculate(
            self.sessions, {'FUND': '1000'}, self.prices, self.identities,
            self.trades, self.settlements, {'2026-07-02': [action]},
            self.transfers, {'2026-07-03': [payment]})
        self.assertEqual(daily[-1]['settled_cash_usd'], '982')
        self.assertEqual(daily[-1]['dividend_receivable_unconfirmed_usd'], '0')
        self.assertEqual(daily[-1]['illustrative_nav_usd'], '1006')
        self.assertEqual(entitlements[0]['payment_status'], 'MATCHED')

    def test_payment_cannot_exceed_entitlement(self):
        action = dict(self.dividends['2026-07-02'][0], ticker='XOM',
                      pay_date='2026-07-03', review_status='APPROVED_IN_SEED')
        payment = dict(event_id='p1', account_id='FUND', corporate_action_id='d1',
                       instrument_id='XOM.US', currency='USD', cash_amount='3',
                       settlement_date='2026-07-03',
                       settled_at='2026-07-03T18:00:00+00:00',
                       published_at='2026-07-03T18:01:00+00:00',
                       event_type='DIVIDEND_PAYMENT_CONFIRMED',
                       source_system='simulated_custodian', is_simulated=True)
        with self.assertRaisesRegex(ValueError, 'exceeds entitlement'):
            calculate(self.sessions, {'FUND': '1000'}, self.prices, self.identities,
                      self.trades, self.settlements, {'2026-07-02': [action]},
                      self.transfers, {'2026-07-03': [payment]})

    def test_reviewed_payment_and_pending_candidate_are_separate(self):
        approved = dict(self.dividends['2026-07-02'][0], ticker='XOM',
                        pay_date='2026-07-03', review_status='APPROVED_IN_SEED')
        pending = dict(approved, event_id='d2', cash_amount='0.5',
                       review_status='PENDING')
        payment = dict(event_id='p1', account_id='FUND', corporate_action_id='d1',
                       instrument_id='XOM.US', currency='USD', cash_amount='2',
                       settlement_date='2026-07-03',
                       settled_at='2026-07-03T18:00:00+00:00',
                       published_at='2026-07-03T18:01:00+00:00',
                       event_type='DIVIDEND_PAYMENT_CONFIRMED',
                       source_system='simulated_custodian', is_simulated=True)
        daily, _, _, _ = calculate(
            self.sessions, {'FUND': '1000'}, self.prices, self.identities,
            self.trades, self.settlements, {'2026-07-02': [approved, pending]},
            self.transfers, {'2026-07-03': [payment]}, show_review_split=True)
        self.assertEqual(daily[-1]['settled_cash_usd'], '982')
        self.assertEqual(Decimal(daily[-1]['reviewed_dividend_receivable_usd']), 0)
        self.assertEqual(Decimal(daily[-1]['pending_dividend_receivable_usd']), 1)
        self.assertEqual(Decimal(daily[-1]['nav_excluding_pending_actions_usd']), 1006)
        self.assertEqual(Decimal(daily[-1]['illustrative_nav_usd']), 1007)

    def test_pending_short_dividend_reduces_only_illustrative_nav(self):
        trades = copy.deepcopy(self.trades)
        trades['2026-07-01'][0]['side'] = 'SELL'
        settlements = copy.deepcopy(self.settlements)
        settlements['2026-07-02'][0]['side'] = 'SELL'
        settlements['2026-07-02'][0]['cash_amount'] = '20'
        daily, _, _, _ = calculate(
            self.sessions, {'FUND': '1000'}, self.prices, self.identities,
            trades, settlements, self.dividends, self.transfers,
            show_review_split=True)
        self.assertEqual(daily[1]['pending_short_dividend_payable_usd'], '2')
        self.assertEqual(daily[1]['pending_candidate_impact_usd'], '-2')
        self.assertEqual(daily[1]['nav_excluding_pending_actions_usd'], '998')
        self.assertEqual(daily[1]['illustrative_nav_usd'], '996')


if __name__ == '__main__':
    unittest.main()
