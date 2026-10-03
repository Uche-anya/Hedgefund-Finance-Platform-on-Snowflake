import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from simulation.historical_simulator import produce_trades, reference_prices


def sample(extra=()):
    file = io.StringIO()
    writer = csv.writer(file)
    writer.writerow(['valuation_date', 'universe_ticker', 'source_ticker', 'currency', 'price_basis', 'close_price'])
    writer.writerows([
        ['2025-01-03', 'AAPL', 'AAPL', 'USD', 'unadjusted', '100'],
        ['2025-01-03', 'AMZN', 'AMZN', 'USD', 'unadjusted', '200'],
        *extra,
    ])
    return file.getvalue().encode()


class HistoricalSimulatorTests(unittest.TestCase):
    def test_future_prices_do_not_affect_reference(self):
        base = sample()
        future = sample([['2025-01-06', 'AAPL', 'AAPL', 'USD', 'unadjusted', '999']])
        self.assertEqual(reference_prices(base), reference_prices(future))

    def test_duplicate_and_missing_prices_are_rejected(self):
        with self.assertRaises(ValueError):
            reference_prices(sample([['2025-01-03', 'AAPL', 'AAPL', 'USD', 'unadjusted', '101']]))
        with self.assertRaises(ValueError):
            reference_prices(sample().replace(b'AMZN', b'OTHER'))

    def test_produces_traceable_fictional_events_and_rejects_changed_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = sample()
            (root / 'prices.csv').write_bytes(payload)
            (root / 'manifest.json').write_text(json.dumps({
                'output_sha256': {'prices.csv': hashlib.sha256(payload).hexdigest()}}))
            with patch('builtins.print'):
                folder = produce_trades(root, root / 'events')
            records = [json.loads(p.read_text()) for p in folder.glob('*.jsonl')]
            self.assertEqual(len(records), 5)
            first = min(records, key=lambda r: r['executed_at'])
            self.assertEqual(first['execution_price'], '100.05')
            self.assertTrue(all(r['is_simulated'] for r in records))
            self.assertTrue(all(r['reference_price_date'] < r['business_date'] for r in records))
            manifest = json.loads((folder / 'manifest.json').read_text())
            self.assertTrue(all(hashlib.sha256((folder / f).read_bytes()).hexdigest() == h
                                for f, h in manifest['files'].items()))
            (root / 'prices.csv').write_bytes(payload + b'\n')
            with self.assertRaises(ValueError):
                produce_trades(root, root / 'events')
