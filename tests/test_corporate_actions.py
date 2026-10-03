import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from data_extraction import corporate_actions as ca


class CorporateActionsTests(unittest.TestCase):
    def test_pagination_resume_and_candidate_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            ca.save(folder / 'request.json', {'start': '2025-01-01', 'end': '2025-01-31', 'symbols': ['AAPL']})
            ca.save(folder / 'manifest.json', {'status': 'INCOMPLETE', 'pages': {}})
            pages = [
                {'status': 'OK', 'results': [{'id': 's1', 'ticker': 'AAPL', 'execution_date': '2025-01-02'}],
                 'next_url': 'https://api.massive.com/stocks/v1/splits?cursor=abc&apiKey=secret'},
                {'status': 'OK', 'results': [{'id': 's2', 'ticker': 'OTHER', 'execution_date': '2025-01-03'}]},
                {'status': 'OK', 'results': []}]
            with patch.object(ca, 'fetch', side_effect=pages), patch.object(ca.time, 'sleep'), patch('builtins.print'):
                ca.download(folder, 'secret')
            self.assertEqual(len((folder / 'splits.jsonl').read_text().splitlines()), 1)
            self.assertEqual((folder / 'dividends.jsonl').read_text(), '')
            self.assertNotIn('secret', (folder / 'splits_0001.json').read_text())
            with patch.object(ca, 'fetch') as fetch, patch('builtins.print'):
                ca.download(folder, 'secret')
                fetch.assert_not_called()
            (folder / 'splits_0001.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'Saved page changed'):
                ca.download(folder, 'secret')

    def test_rejects_foreign_pagination_host(self):
        with self.assertRaises(ValueError):
            ca.clean_url('https://example.org/stocks/v1/splits', 'splits')
