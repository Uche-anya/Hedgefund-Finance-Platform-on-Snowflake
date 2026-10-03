import json
from pathlib import Path
import tempfile
import unittest

from scripts import run_control


class RunControlTests(unittest.TestCase):
    def write_project(self, root, delivery='delivery-1', rows=2):
        (root / 'dbt/models').mkdir(parents=True, exist_ok=True)
        (root / 'dbt/tests').mkdir(exist_ok=True)
        (root / 'dbt/seeds').mkdir(exist_ok=True)
        (root / 'scripts').mkdir(exist_ok=True)
        (root / 'dbt/dbt_project.yml').write_text('name: test\n')
        (root / 'scripts/load_daily_inputs.py').write_text('# loader\n')
        folder = root / 'data/source' / delivery
        folder.mkdir(parents=True)
        manifest = {'delivery_id': delivery, 'record_count': rows}
        manifest_path = folder / 'manifest.json'
        manifest_path.write_text(json.dumps(manifest))
        config = {
            'run_mode': 'DAILY', 'business_date': '2026-10-02',
            'calculation_cutoff': '2026-10-03T08:00:00+00:00',
            'inputs': [{'source_name': 'source', 'delivery_id': delivery,
                        'manifest': f'data/source/{delivery}/manifest.json',
                        'expected_rows': rows}],
            'dbt_vars': {},
        }
        config_path = root / 'config.json'
        config_path.write_text(json.dumps(config))
        return config_path

    def test_exact_retry_keeps_run_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.write_project(root)
            first = run_control.read_config(path, root)
            second = run_control.read_config(path, root)
            self.assertEqual(first['run_id'], second['run_id'])

    def test_changed_delivery_changes_run_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first_path = self.write_project(root)
            first = run_control.read_config(first_path, root)
            second_path = self.write_project(root, 'delivery-2', 3)
            second = run_control.read_config(second_path, root)
            self.assertNotEqual(first['run_id'], second['run_id'])

    def test_wrong_expected_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = self.write_project(root)
            config = json.loads(path.read_text())
            config['inputs'][0]['expected_rows'] = 3
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'manifest rows'):
                run_control.read_config(path, root)


if __name__ == '__main__':
    unittest.main()
