import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import load_oms_snowpipe
from simulation.simulator import create_execution


class OmsSnowpipeTests(unittest.TestCase):
    def write_events(self, folder, count=2):
        path = Path(folder) / 'events.jsonl'
        events = [create_execution(seconds_after_start=index) for index in range(count)]
        path.write_text(''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')
        return path, events

    def test_file_is_validated_and_hash_is_repeatable(self):
        with tempfile.TemporaryDirectory() as folder:
            path, _ = self.write_events(folder)
            first = load_oms_snowpipe.inspect_file(path)
            second = load_oms_snowpipe.inspect_file(path)
            self.assertEqual(first, second)
            self.assertEqual(first[0], 2)
            self.assertEqual(
                load_oms_snowpipe.delivery_name(first[1]),
                'oms-' + first[1][:24],
            )

    def test_duplicate_event_is_rejected_before_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            path, events = self.write_events(folder, 1)
            path.write_text((json.dumps(events[0]) + '\n') * 2, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Duplicate event_id'):
                load_oms_snowpipe.inspect_file(path)

    def test_bad_delivery_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'delivery ID'):
            load_oms_snowpipe.delivery_name('abc', '../wrong')

    def test_wait_stops_when_expected_count_arrives(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [(0,), (2,)]
        with patch('scripts.load_oms_snowpipe.time.sleep'):
            rows = load_oms_snowpipe.wait_for_rows(
                cursor, 'oms-1', expected_rows=2, timeout=10, pause=0
            )
        self.assertEqual(rows, 2)
        self.assertEqual(cursor.execute.call_count, 2)

    def test_notify_requires_success_response(self):
        manager = Mock()
        manager.ingest_files.return_value = {'responseCode': 'FAILURE'}
        staged_file = Mock()
        with patch.dict('sys.modules', {
            'snowflake.ingest': Mock(SimpleIngestManager=Mock(return_value=manager),
                                    StagedFile=staged_file)
        }):
            with self.assertRaisesRegex(RuntimeError, 'Snowpipe rejected'):
                load_oms_snowpipe.notify_pipe('delivery/events.jsonl.gz', 'key')

    def test_existing_delivery_must_match_registry(self):
        cursor = Mock()
        cursor.fetchall.return_value = [('hash', 2, 2, 'READY')]
        load_oms_snowpipe.register_delivery(cursor, 'oms-1', 'hash', 2)
        self.assertEqual(cursor.execute.call_count, 1)

        cursor.fetchall.return_value = [('different', 2, 2, 'READY')]
        with self.assertRaisesRegex(ValueError, 'Conflicting delivery'):
            load_oms_snowpipe.register_delivery(cursor, 'oms-1', 'hash', 2)


if __name__ == '__main__':
    unittest.main()
