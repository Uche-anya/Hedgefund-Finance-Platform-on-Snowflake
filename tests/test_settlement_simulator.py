from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from simulation.simulator import create_execution
from simulation.settlement_simulator import EXPECTED, SCENARIO, produce_settlements


def saved_trades(folder, duplicate=False):
    files = {}
    first_id = None
    for index, (ticker, side, quantity, price) in enumerate(EXPECTED):
        trade = create_execution(ticker + '.US', side, quantity, price, index * 2)
        trade.update(scenario_id=SCENARIO, market_ticker=ticker)
        if index == 0:
            first_id = trade['execution_id']
        if duplicate and index == 1:
            trade['execution_id'] = first_id
        path = folder / (trade['event_id'] + '.jsonl')
        path.write_text(json.dumps(trade) + '\n', encoding='utf-8')
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (folder / 'manifest.json').write_text(json.dumps({
        'scenario_id': SCENARIO, 'event_count': 5, 'files': files}), encoding='utf-8')


class SettlementSimulatorTests(unittest.TestCase):
    def test_four_confirmations_one_missing_and_stable_retry_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            saved_trades(root)
            with patch('builtins.print'):
                folder = produce_settlements(root, root / 'out')
                retry = produce_settlements(root, root / 'out')
            records = [json.loads(p.read_text()) for p in folder.glob('*.jsonl')]
            self.assertEqual(len(records), 4)
            self.assertEqual(sum(Decimal(r['cash_amount']) for r in records), Decimal('-2532.87'))
            self.assertTrue(all(r['is_simulated'] for r in records))
            self.assertFalse(any(r['instrument_id'] == 'AMZN.US' and r['side'] == 'BUY' for r in records))
            manifest = json.loads((folder / 'manifest.json').read_text())
            self.assertEqual(len(manifest['unconfirmed_execution_ids']), 1)
            self.assertTrue(all(r['published_at'] <= manifest['as_of'] for r in records))
            self.assertEqual(manifest['files'], json.loads((retry / 'manifest.json').read_text())['files'])
            for name, digest in manifest['files'].items():
                self.assertEqual(hashlib.sha256((folder / name).read_bytes()).hexdigest(), digest)

    def test_changed_input_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            saved_trades(root)
            file = next(root.glob('*.jsonl'))
            file.write_bytes(file.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'Changed input'):
                produce_settlements(root, root / 'out')
            self.assertFalse((root / 'out').exists())

    def test_repeated_trade_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            saved_trades(root, duplicate=True)
            with self.assertRaisesRegex(ValueError, 'Duplicate execution_id'):
                produce_settlements(root, root / 'out')


if __name__ == '__main__':
    unittest.main()
