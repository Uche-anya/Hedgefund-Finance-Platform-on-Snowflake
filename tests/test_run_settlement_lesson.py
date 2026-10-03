import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import run_settlement_lesson as runner


class SettlementRunnerTests(unittest.TestCase):
    def test_failed_load_stops_before_dbt_and_records_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            python = root / '.venv/dbt/Scripts/python.exe'
            python.parent.mkdir(parents=True)
            python.touch()
            with patch.object(runner, 'verify_inputs', return_value=[]), \
                    patch.object(runner.subprocess, 'run', return_value=Mock(returncode=5)) as run, \
                    patch('builtins.print'):
                code = runner.run_pipeline(root)
            self.assertEqual(code, 5)
            self.assertEqual(run.call_count, 1)
            record = json.loads(next((root / 'data/pipeline_runs').glob('*/run.json')).read_text())
            self.assertEqual(record['status'], 'FAILED')
            self.assertEqual(record['steps'][0]['exit_code'], 5)

    def test_success_runs_loads_before_dbt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            python = root / '.venv/dbt/Scripts/python.exe'
            python.parent.mkdir(parents=True)
            python.touch()
            with patch.object(runner, 'verify_inputs', return_value=[]), \
                    patch.object(runner.subprocess, 'run', return_value=Mock(returncode=0)) as run, \
                    patch('builtins.print'):
                self.assertEqual(runner.run_pipeline(root), 0)
            self.assertEqual(run.call_count, 3)
            self.assertIn('16_settlement_events.sql', run.call_args_list[0].args[0][-1])
            self.assertIn('17_late_settlement.sql', run.call_args_list[1].args[0][-1])
            self.assertEqual(run.call_args_list[2].args[0][1], 'scripts/dbt_dev.py')
            record = json.loads(next((root / 'data/pipeline_runs').glob('*/run.json')).read_text())
            self.assertEqual(record['status'], 'SUCCEEDED')

    def test_changed_delivery_fails_before_any_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            delivery = next(iter(runner.DELIVERIES))
            folder = root / 'data/simulator_settlements' / delivery
            folder.mkdir(parents=True)
            files = {}
            for index in range(4):
                name = f'event-{index}.jsonl'
                (folder / name).write_bytes(b'{}\n')
                files[name] = hashlib.sha256(b'{}\n').hexdigest()
            (folder / 'manifest.json').write_text(json.dumps({
                'delivery_id': delivery, 'event_count': 4, 'files': files}))
            (folder / 'event-0.jsonl').write_bytes(b'changed')
            with patch.object(runner.subprocess, 'run') as run, patch('builtins.print'):
                self.assertEqual(runner.run_pipeline(root), 1)
            run.assert_not_called()
