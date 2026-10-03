import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import run_replay as runner


class ReplayRunnerTests(unittest.TestCase):
    def test_failed_build_stops_before_independent_check(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            python = root / '.venv/dbt/Scripts/python.exe'
            python.parent.mkdir(parents=True)
            python.touch()
            with patch.object(runner, 'verify_inputs', return_value={}), \
                    patch.object(runner.subprocess, 'run',
                                 side_effect=[Mock(returncode=0), Mock(returncode=4)]) as run, \
                    patch('builtins.print'):
                self.assertEqual(runner.run_pipeline(root), 4)
            self.assertEqual(run.call_count, 2)
            record = json.loads(next((root / 'data/replay_runs').glob('*/run.json')).read_text())
            self.assertEqual(record['status'], 'FAILED')
            self.assertEqual(record['steps'][-1]['name'], 'build_and_test')

    def test_bad_inputs_stop_before_connecting(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(runner, 'verify_inputs', side_effect=ValueError('Changed input')), \
                    patch.object(runner.subprocess, 'run') as run, patch('builtins.print'):
                self.assertEqual(runner.run_pipeline(Path(temp)), 1)
            run.assert_not_called()
