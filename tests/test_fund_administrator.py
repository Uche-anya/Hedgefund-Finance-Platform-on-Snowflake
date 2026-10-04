import json
from pathlib import Path
import tempfile
import unittest

from simulation.fund_administrator import produce


class FundAdministratorTests(unittest.TestCase):
    def test_saved_delivery_is_reusable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            replay = root / 'replay'
            replay.mkdir()
            (replay / 'manifest.json').write_text(json.dumps({
                'scenario_id': 'TEST-REPLAY',
                'config': {'accounts': ['SIM-REPLAY-01', 'SIM-REPLAY-02']},
            }))
            sessions = [
                {'record_type': 'SESSION', 'business_date': day}
                for day in ('2025-01-31', '2025-02-03', '2025-02-04', '2025-02-07')
            ]
            (replay / 'records.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in sessions))
            config = json.loads((Path(__file__).parents[1] / 'config/fund_admin_january.json').read_text())
            config['source_replay'] = 'replay'
            config_path = root / 'fund_admin.json'
            config_path.write_text(json.dumps(config))
            output = root / 'output'

            first = produce(config_path=config_path, output=output, input_root=root)
            second = produce(config_path=config_path, output=output, input_root=root)
            self.assertEqual(first, second)
            self.assertEqual(len((first / 'events.jsonl').read_text().splitlines()), 4)
