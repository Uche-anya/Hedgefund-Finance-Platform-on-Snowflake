import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.check_daily_readiness import check_raw, saved_inputs


class Cursor:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    def execute(self, statement, parameters):
        self.calls.append((statement, parameters))
        self.rows = next(self.answers)

    def fetchall(self):
        return self.rows


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        oms_folder = self.root / 'oms'
        price_folder = self.root / 'prices'
        oms_folder.mkdir()
        price_folder.mkdir()

        events = [
            {'event_id': 'event-1', 'execution_id': 'exec-1',
             'scenario_id': 'test-scenario', 'business_date': '2026-09-22',
             'published_at': '2026-09-22T15:00:00Z'},
            {'event_id': 'event-2', 'execution_id': 'exec-2',
             'scenario_id': 'test-scenario', 'business_date': '2026-09-22',
             'published_at': '2026-09-22T15:01:00Z'},
        ]
        oms_file = oms_folder / 'oms.jsonl'
        oms_file.write_text(''.join(json.dumps(row) + '\n' for row in events),
                            encoding='utf-8')
        price_file = price_folder / 'prices.csv'
        price_file.write_text(
            'valuation_date,universe_ticker,currency,price_basis,close_price\n'
            '2026-09-22,AAPL,USD,unadjusted,245.00\n'
            '2026-09-22,AMZN,USD,unadjusted,227.61\n', encoding='utf-8')
        def hash_file(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        (oms_folder / 'manifest.json').write_text(json.dumps({
            'business_date': '2026-09-22', 'scenario_id': 'test-scenario',
            'delivery_id': 'oms-test', 'record_count': 2,
            'files': {'oms.jsonl': hash_file(oms_file)}}), encoding='utf-8')
        (price_folder / 'manifest.json').write_text(json.dumps({
            'valuation_date': '2026-09-22', 'delivery_id': 'price-test',
            'record_count': 2, 'files': {'prices.csv': hash_file(price_file)}}),
            encoding='utf-8')
        self.request = {'scenario_id': 'test-scenario', 'business_date': '2026-09-22',
                        'cutoff_at': '2026-09-22T23:59:59Z',
                        'required_tickers': ['AAPL', 'AMZN'],
                        'oms_manifest': 'oms/manifest.json',
                        'price_manifest': 'prices/manifest.json'}
        self.selected = saved_inputs(self.root, self.request)

    def good_rows(self):
        oms = self.selected['oms']
        prices = self.selected['daily_prices']
        receipts = [[(item['sha256'], item['rows'], item['rows'], 'READY')]
                    for item in (oms, prices)]
        events = [(oms['delivery_id'], event_id, execution_id,
                   '2026-09-22T15:00:00Z', 'ACTIVE')
                  for event_id, execution_id in zip(oms['event_ids'], oms['execution_ids'])]
        bars = [(prices['delivery_id'], ticker, 'USD', 'unadjusted', close)
                for ticker, close in prices['closes'].items()]
        return [*receipts, events, bars]

    def test_retry_uses_same_request_and_accepts_same_rows(self):
        again = saved_inputs(self.root, self.request)
        self.assertEqual(self.selected['request_id'], again['request_id'])
        check_raw(Cursor(self.good_rows()), self.selected)

    def test_changed_cutoff_is_a_new_request(self):
        request = dict(self.request, cutoff_at='2026-09-23T00:00:00Z')
        changed = saved_inputs(self.root, request)
        self.assertNotEqual(self.selected['request_id'], changed['request_id'])

    def test_second_delivery_cannot_repeat_an_event(self):
        rows = self.good_rows()
        rows[2].append(('different-delivery', rows[2][0][1], rows[2][0][2],
                        '2026-09-22T15:00:00Z', 'ACTIVE'))
        with self.assertRaisesRegex(ValueError, 'repeated events'):
            check_raw(Cursor(rows), self.selected)

    def test_changed_receipt_or_price_stops_the_close(self):
        rows = self.good_rows()
        rows[0] = [('wrong-hash', 2, 2, 'READY')]
        with self.assertRaisesRegex(ValueError, 'receipt missing or changed'):
            check_raw(Cursor(rows), self.selected)
        rows = self.good_rows()
        first = rows[3][0]
        rows[3][0] = (*first[:4], '0.01')
        with self.assertRaisesRegex(ValueError, 'RAW price differs'):
            check_raw(Cursor(rows), self.selected)

    def test_corrected_price_request_reads_only_its_delivery(self):
        selected = dict(self.selected)
        selected['daily_prices'] = dict(self.selected['daily_prices'],
                                        replaces_delivery_id='price-old')
        rows = self.good_rows()
        cursor = Cursor(rows)
        check_raw(cursor, selected)
        self.assertIn('delivery_id = %s', cursor.calls[-1][0])
        self.assertEqual(cursor.calls[-1][1], ('2026-09-22', 'price-test'))


if __name__ == '__main__':
    unittest.main()
