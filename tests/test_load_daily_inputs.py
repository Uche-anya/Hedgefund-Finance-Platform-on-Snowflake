import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import load_daily_inputs


class DailyInputLoaderTests(unittest.TestCase):
    def test_manifest_must_name_the_selected_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'data' / 'replay' / 'saved-delivery'
            folder.mkdir(parents=True)
            records = folder / 'records.jsonl'
            records.write_text('{}\n', encoding='utf-8')
            manifest = {
                'delivery_id': 'saved-delivery',
                'files': {'records.jsonl': load_daily_inputs.sha256(records)},
            }
            manifest_path = folder / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
            config = {
                'inputs': [{
                    'source_name': 'activity_events',
                    'delivery_id': 'different-delivery',
                    'manifest': 'data/replay/saved-delivery/manifest.json',
                    'expected_rows': 1,
                }]
            }
            config_path = root / 'config.json'
            config_path.write_text(json.dumps(config), encoding='utf-8')

            with self.assertRaisesRegex(ValueError, 'delivery ID differs'):
                load_daily_inputs.deliveries(root, config_path)

    @mock.patch('snowflake.connector.connect')
    @mock.patch('scripts.load_daily_inputs.serialization.load_pem_private_key')
    @mock.patch('scripts.load_daily_inputs.unlock_secret', return_value='secret')
    @mock.patch('pathlib.Path.read_bytes', return_value=b'key')
    def test_connection_disables_autocommit(self, _read, _secret, load_key, connect):
        key = mock.Mock()
        key.private_bytes.return_value = b'private-key'
        load_key.return_value = key

        load_daily_inputs.connect()

        self.assertFalse(connect.call_args.kwargs['autocommit'])


if __name__ == '__main__':
    unittest.main()
