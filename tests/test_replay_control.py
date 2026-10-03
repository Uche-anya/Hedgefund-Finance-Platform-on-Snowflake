from decimal import Decimal
import unittest

from fund_pipeline.replay_control import calculate


class ReplayControlTests(unittest.TestCase):
    def records(self):
        return [
            dict(record_type='OPENING_CASH', account_id='A', amount='100'),
            dict(record_type='SESSION', business_date='2025-01-06', cutoff='2025-01-06T22:00:00+00:00'),
            dict(record_type='SESSION', business_date='2025-01-07', cutoff='2025-01-07T22:00:00+00:00'),
            dict(record_type='EXECUTION', execution_id='E', account_id='A', market_ticker='AAPL',
                 business_date='2025-01-06', side='BUY', quantity='2', execution_price='10'),
            dict(record_type='SETTLEMENT', execution_id='E', cash_amount='-20',
                 settled_at='2025-01-07T17:00:00+00:00', published_at='2025-01-07T17:01:00+00:00')]

    def test_hand_calculated_cash_and_nav_with_no_trades_next_day(self):
        prices = {('2025-01-06', 'AAPL'): Decimal('12'), ('2025-01-07', 'AAPL'): Decimal('11')}
        positions, balances = calculate(self.records(), prices, ['AAPL'])
        self.assertEqual(balances[('2025-01-06', 'A')]['simplified_nav'], Decimal('104'))
        self.assertEqual(balances[('2025-01-06', 'A')]['payables'], Decimal('20'))
        self.assertEqual(balances[('2025-01-07', 'A')]['reported_settled_cash'], Decimal('80'))
        self.assertEqual(balances[('2025-01-07', 'A')]['simplified_nav'], Decimal('102'))
        self.assertEqual(positions[('2025-01-07', 'A', 'AAPL.US')]['closing_quantity'], Decimal('2'))

    def test_delayed_reporting_changes_cash_and_payable_but_not_nav(self):
        rows = self.records()
        rows[-1]['published_at'] = '2025-01-08T09:00:00+00:00'
        prices = {('2025-01-06', 'AAPL'): Decimal('12'), ('2025-01-07', 'AAPL'): Decimal('11')}
        _, balances = calculate(rows, prices, ['AAPL'])
        self.assertEqual(balances[('2025-01-07', 'A')]['reported_settled_cash'], Decimal('100'))
        self.assertEqual(balances[('2025-01-07', 'A')]['payables'], Decimal('20'))
        self.assertEqual(balances[('2025-01-07', 'A')]['simplified_nav'], Decimal('102'))

    def test_dividend_stays_fixed_after_ex_date_trades_and_does_not_change_cash(self):
        rows = self.records()
        rows.append(dict(record_type='SESSION', business_date='2025-01-08',
                         cutoff='2025-01-08T22:00:00+00:00'))
        rows.append(dict(record_type='EXECUTION', execution_id='LATER', account_id='A',
                         market_ticker='AAPL', business_date='2025-01-07', side='BUY',
                         quantity='3', execution_price='11'))
        prices = {(day, 'AAPL'): Decimal('11')
                  for day in ['2025-01-06', '2025-01-07', '2025-01-08']}
        dividend = [dict(ticker='AAPL', ex_date='2025-01-07', pay_date='2025-02-07', amount='0.50')]
        _, base = calculate(rows, prices, ['AAPL'])
        _, result = calculate(rows, prices, ['AAPL'], dividend)
        for day in ['2025-01-06', '2025-01-07', '2025-01-08']:
            expected = Decimal('0') if day == '2025-01-06' else Decimal('1')
            self.assertEqual(result[(day, 'A')]['dividend_receivable'], expected)
            self.assertEqual(result[(day, 'A')]['simplified_nav'],
                             base[(day, 'A')]['simplified_nav'] + expected)
            self.assertEqual(result[(day, 'A')]['reported_settled_cash'],
                             base[(day, 'A')]['reported_settled_cash'])

    def test_short_dividend_reduces_nav_without_changing_cash(self):
        rows = self.records()[:-1]
        rows[-1]['side'] = 'SELL'
        prices = {(day, 'AAPL'): Decimal('11') for day in ['2025-01-06', '2025-01-07']}
        dividend = [dict(ticker='AAPL', ex_date='2025-01-07', pay_date='2025-02-07', amount='0.50')]
        _, result = calculate(rows, prices, ['AAPL'], dividend)
        day = result[('2025-01-07', 'A')]
        self.assertEqual(day['dividend_receivable'], Decimal('0'))
        self.assertEqual(day['short_dividend_payable'], Decimal('1'))
        self.assertEqual(day['simplified_nav'], day['nav_before_dividends'] - 1)
        self.assertEqual(day['reported_settled_cash'], Decimal('100'))

    def test_payment_date_alone_does_not_move_cash(self):
        rows = self.records()
        prices = {(day, 'AAPL'): Decimal('11') for day in ['2025-01-06', '2025-01-07']}
        dividend = [dict(ticker='AAPL', ex_date='2025-01-06', pay_date='2025-01-07', amount='0.50')]
        dividend[0]['ex_date'] = '2025-01-07'
        _, result = calculate(rows, prices, ['AAPL'], dividend)
        self.assertEqual(result[('2025-01-07', 'A')]['dividend_receivable'], Decimal('1'))
        self.assertEqual(result[('2025-01-07', 'A')]['confirmed_dividend_cash'], Decimal('0'))

    def test_dividend_confirmation_moves_receivable_into_cash_without_new_nav(self):
        rows = self.records()
        rows.append(dict(record_type='SESSION', business_date='2025-01-08',
                         cutoff='2025-01-08T22:00:00+00:00'))
        prices = {(day, 'AAPL'): Decimal('11')
                  for day in ['2025-01-06', '2025-01-07', '2025-01-08']}
        dividend = [dict(ticker='AAPL', ex_date='2025-01-07', pay_date='2025-01-07',
                         amount='0.50', event_id='D')]
        _, unpaid = calculate(rows, prices, ['AAPL'], dividend)
        payment = dict(record_type='DIVIDEND_PAYMENT', corporate_action_id='D', account_id='A',
                       currency='USD', instrument_id='AAPL.US', cash_amount='1.00',
                       settled_at='2025-01-07T18:00:00+00:00', published_at='2025-01-08T09:00:00+00:00')
        rows.append(payment)
        _, paid = calculate(rows, prices, ['AAPL'], dividend)
        self.assertEqual(paid[('2025-01-07', 'A')]['dividend_receivable'], Decimal('1'))
        self.assertEqual(paid[('2025-01-07', 'A')]['confirmed_dividend_cash'], Decimal('0'))
        self.assertEqual(paid[('2025-01-08', 'A')]['dividend_receivable'], Decimal('0'))
        self.assertEqual(paid[('2025-01-08', 'A')]['confirmed_dividend_cash'], Decimal('1'))
        for day in ['2025-01-06', '2025-01-07', '2025-01-08']:
            self.assertEqual(paid[(day, 'A')]['simplified_nav'], unpaid[(day, 'A')]['simplified_nav'])
        self.assertEqual(paid[('2025-01-08', 'A')]['reported_settled_cash'],
                         unpaid[('2025-01-08', 'A')]['reported_settled_cash'] + 1)
        with self.assertRaisesRegex(ValueError, 'Duplicate dividend'):
            calculate(rows + [payment], prices, ['AAPL'], dividend)
        payment['cash_amount'] = '2.00'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            calculate(rows, prices, ['AAPL'], dividend)
