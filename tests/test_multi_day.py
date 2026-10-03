from decimal import Decimal
import unittest

from simulation.multi_day import build_records, next_settlement_day


class MultiDayTests(unittest.TestCase):
    def config(self):
        return dict(start_date='2025-01-06', end_date='2025-01-08', seed=1,
                    trades_per_day=100, no_trade_dates=['2025-01-07'],
                    tickers=['AAPL'], accounts=['SIM-01'], opening_cash_usd='1000000',
                    settlement_closed_dates=['2025-01-01', '2025-01-20'],
                    settlement_calendar_end='2025-02-04')

    def test_trading_closure_does_not_shift_settlement(self):
        self.assertEqual(next_settlement_day('2025-01-08', self.config()), '2025-01-09')
        self.assertEqual(next_settlement_day('2025-01-17', self.config()), '2025-01-21')

    def test_deterministic_no_trade_day_and_no_future_price_use(self):
        config = self.config()
        days = ['2025-01-03', '2025-01-06', '2025-01-07', '2025-01-08']
        prices = {(day, 'AAPL'): Decimal('100') for day in days}
        rows = build_records(config, prices, days, 'test')
        self.assertEqual(rows, build_records(config, prices, days, 'test'))
        executions = [r for r in rows if r['record_type'] == 'EXECUTION']
        self.assertEqual(len(executions), 200)
        self.assertFalse(any(r['business_date'] == '2025-01-07' for r in executions))
        self.assertTrue(all(r['reference_price_date'] < r['business_date'] for r in executions))
        prices[('2025-01-08', 'AAPL')] = Decimal('999')
        self.assertEqual(rows, build_records(config, prices, days, 'test'))
        settlements = [r for r in rows if r['record_type'] == 'SETTLEMENT']
        self.assertEqual(len(settlements), 198)
        self.assertTrue(any(r['published_at'][:10] > r['settlement_date'] for r in settlements))
