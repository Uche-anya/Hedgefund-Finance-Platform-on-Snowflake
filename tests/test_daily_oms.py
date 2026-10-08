import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from simulation.daily_oms import generate, generate_next_day, make_day


class DailyOmsTests(unittest.TestCase):
    def test_new_day_uses_checked_daily_close(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prices = root / 'prices.csv'
            with prices.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    'valuation_date', 'universe_ticker', 'source_ticker',
                    'currency', 'price_basis', 'close_price'])
                writer.writeheader()
                writer.writerow(dict(valuation_date='2026-09-22', universe_ticker='AAPL',
                                     source_ticker='AAPL', currency='USD',
                                     price_basis='unadjusted', close_price='339.75'))
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({
                'valuation_date': '2026-09-22',
                'files': {'prices.csv': hashlib.sha256(prices.read_bytes()).hexdigest()}}))
            config = root / 'config.json'
            config.write_text(json.dumps({
                'scenario_id': 'daily', 'end_date': '2026-09-18', 'seed': 1,
                'trades_per_day': 1, 'accounts': ['A'], 'tickers': ['AAPL']}))
            folder = generate_next_day(config, '2026-09-23', '2026-09-24',
                                       output=root / 'oms', previous_prices_manifest=manifest)
            event = json.loads((folder / 'oms.jsonl').read_text().strip())
            self.assertEqual(event['reference_price_date'], '2026-09-22')
            self.assertEqual(event['reference_close_price'], '339.75')
            self.assertEqual(json.loads((folder / 'manifest.json').read_text())
                             ['price_snapshot_sha256'], hashlib.sha256(prices.read_bytes()).hexdigest())
            prices.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Previous daily price delivery changed'):
                generate_next_day(config, '2026-09-23', '2026-09-24',
                                  output=root / 'oms', previous_prices_manifest=manifest)

    def test_fills_use_yesterday_and_delivery_is_repeatable(self):
        config = {'scenario_id': 'pilot', 'seed': 7, 'trades_per_day': 2,
                  'accounts': ['A', 'B'], 'tickers': ['AAPL', 'AMZN']}
        prices = {('2024-09-23', 'AAPL'): Decimal('100'),
                  ('2024-09-23', 'AMZN'): Decimal('200')}
        events = make_day(config, '2024-09-24', '2024-09-23', '2024-09-25', prices)
        self.assertEqual(events, make_day(config, '2024-09-24', '2024-09-23',
                                          '2024-09-25', prices))
        self.assertEqual({row['reference_price_date'] for row in events}, {'2024-09-23'})
        self.assertEqual({row['settlement_due'] for row in events}, {'2024-09-25'})
        self.assertEqual(len({row['execution_id'] for row in events}), 2)

    def test_dollar_budget_uses_previous_close(self):
        config = {'scenario_id': 'dollar-test', 'seed': 7, 'trades_per_day': 2,
                  'accounts': ['A', 'B'], 'tickers': ['AAPL'],
                  'sizing_method': 'dollar_budget',
                  'min_trade_usd': 25000, 'max_trade_usd': 45000}
        prices = {('2024-09-23', 'AAPL'): Decimal('100')}
        events = make_day(config, '2024-09-24', '2024-09-23', '2024-09-25', prices)
        self.assertEqual(events, make_day(config, '2024-09-24',
                                          '2024-09-23', '2024-09-25', prices))
        for event in events:
            shares = Decimal(event['quantity'])
            self.assertGreater(shares * Decimal('100'), Decimal('24900'))
            self.assertLessEqual(shares * Decimal('100'), Decimal('45000'))

    def test_saved_daily_file_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            price_file = root / 'prices.csv'
            with price_file.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=[
                    'valuation_date', 'universe_ticker', 'source_ticker',
                    'currency', 'price_basis', 'close_price'])
                writer.writeheader()
                for day in ('2024-09-23', '2024-09-24', '2024-09-25', '2024-09-26'):
                    for ticker in ('AAPL', 'AMZN'):
                        writer.writerow(dict(valuation_date=day, universe_ticker=ticker,
                                             source_ticker=ticker, currency='USD',
                                             price_basis='unadjusted', close_price='100'))
            settings = {'scenario_id': 'test-daily', 'start_date': '2024-09-24',
                        'end_date': '2024-09-25', 'seed': 1, 'trades_per_day': 2,
                        'accounts': ['A', 'B'], 'tickers': ['AAPL', 'AMZN'],
                        'price_file': str(price_file),
                        'price_sha256': hashlib.sha256(price_file.read_bytes()).hexdigest()}
            config = root / 'config.json'
            config.write_text(json.dumps(settings))
            output = root / 'daily'
            self.assertEqual(generate(config, output), ['2024-09-24', '2024-09-25'])
            first = output / 'test-daily/2024-09-24/oms.jsonl'
            saved = first.read_bytes()
            generate(config, output)
            self.assertEqual(first.read_bytes(), saved)
            self.assertEqual(generate(config, output, selected_day='2024-09-25'),
                             ['2024-09-25'])
            with self.assertRaisesRegex(ValueError, 'not a selected market date'):
                generate(config, output, selected_day='2024-09-26')
            first.write_text('changed\n')
            with self.assertRaisesRegex(ValueError, 'Saved delivery changed'):
                generate(config, output)


if __name__ == '__main__':
    unittest.main()
