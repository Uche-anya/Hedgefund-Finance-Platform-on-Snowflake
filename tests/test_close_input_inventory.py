import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.inventory_close_inputs import (daily_price_packages, dated_packages,
                                            package, selection_id)
from scripts.verify_close_inventory import compare


class CloseInputInventoryTests(unittest.TestCase):
    def test_next_close_keeps_prior_provider_prices(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / 'data/daily_prices'
            for name, day, provider in (
                    ('prior', '2026-09-22', True),
                    ('dev_correction', '2026-09-22', False),
                    ('current', '2026-09-23', True)):
                folder = base / name
                folder.mkdir(parents=True)
                file = folder / 'prices.csv'
                file.write_text(name + '\n', encoding='utf-8')
                manifest = {'delivery_id': name, 'valuation_date': day,
                            'record_count': 1,
                            'files': {'prices.csv': hashlib.sha256(file.read_bytes()).hexdigest()}}
                if provider:
                    manifest['source_snapshot'] = 'data/historical_prices/' + name
                (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            from datetime import date
            chosen = daily_price_packages(root, date(2026, 9, 23),
                                          'data/daily_prices/current/manifest.json')
            self.assertEqual({item['delivery_id'] for item in chosen},
                             {'prior', 'current'})

    def test_changed_file_fails_before_it_can_be_selected(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'delivery'
            folder.mkdir()
            file = folder / 'oms.jsonl'
            file.write_text('{"event_id":"one"}\n', encoding='utf-8')
            manifest = {
                'delivery_id': 'oms-one', 'record_count': 1,
                'files': {'oms.jsonl': hashlib.sha256(file.read_bytes()).hexdigest()},
            }
            (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(package(root, folder / 'manifest.json',
                                     'oms.jsonl', 'oms_events')['expected_rows'], 1)
            file.write_text('{"event_id":"changed"}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'changed since packaging'):
                package(root, folder / 'manifest.json', 'oms.jsonl', 'oms_events')

    def test_next_day_settlement_is_outside_today_close(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            for day in ('2026-09-22', '2026-09-23'):
                folder = root / 'data/daily_settlements/demo' / day
                folder.mkdir(parents=True)
                file = folder / 'settlements.jsonl'
                file.write_text('{"event_id":"' + day + '"}\n', encoding='utf-8')
                manifest = {
                    'delivery_id': day, 'scenario_id': 'demo', 'record_count': 1,
                    'files': {'settlements.jsonl': hashlib.sha256(file.read_bytes()).hexdigest()},
                }
                (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            from datetime import date
            chosen = dated_packages(root, 'daily_settlements', 'demo',
                                    date(2026, 9, 22), 'settlements.jsonl',
                                    'settlement_events')
            self.assertEqual([item['delivery_id'] for item in chosen], ['2026-09-22'])

    def test_raw_or_receipt_change_fails_the_close(self):
        item = {'source_name': 'oms_events', 'delivery_id': 'oms-one',
                'expected_rows': 2, 'receipt_sha256': 'file-hash'}
        selected = {'inputs': [item]}
        key = ('oms_events', 'oms-one')
        good_receipt = {key: ('file-hash', 2, 2, 'READY')}
        self.assertEqual(compare(selected, {key: 2}, good_receipt, []), ([], []))
        errors, _ = compare(selected, {key: 3}, good_receipt, [key])
        self.assertTrue(any('RAW 3' in error for error in errors))
        self.assertTrue(any('duplicate receipt' in error for error in errors))

    def test_unreceipted_baseline_is_reported_as_gap(self):
        item = {'source_name': 'historical_prices', 'delivery_id': 'baseline',
                'expected_rows': 2, 'receipt_sha256': None}
        errors, gaps = compare({'inputs': [item]},
                               {('historical_prices', 'baseline'): 2}, {}, [])
        self.assertEqual(errors, [])
        self.assertEqual(len(gaps), 1)

    def test_corrected_delivery_creates_a_new_request(self):
        selection = {
            'scenario_id': 'demo', 'business_date': '2026-09-22',
            'cutoff_at': '2026-09-22T23:59:59+00:00',
            'model_sha256': 'model-1', 'seed_sha256': 'seed-1',
            'inputs': [{'source_name': 'oms_events', 'delivery_id': 'first',
                        'file_sha256': 'original', 'expected_rows': 1}],
        }
        first = selection_id(selection)
        self.assertEqual(first, selection_id(selection))

        corrected = json.loads(json.dumps(selection))
        corrected['inputs'][0]['delivery_id'] = 'correction'
        corrected['inputs'][0]['file_sha256'] = 'new-bytes'
        self.assertNotEqual(first, selection_id(corrected))


if __name__ == '__main__':
    unittest.main()
