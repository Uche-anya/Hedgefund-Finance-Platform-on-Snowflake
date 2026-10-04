import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import snow_admin


class SnowAdminTests(unittest.TestCase):
    def test_deployment_copy_includes_environment_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'dbt'
            for name in ('models', 'tests', 'seeds'):
                folder = source / name
                folder.mkdir(parents=True)
                (folder / 'keep.txt').write_text(name)
            for name in ('dbt_project.yml', 'dbt_projects_profiles.yml', 'env.yml'):
                (source / name).write_text(f'{name}: true\n')
            (source / 'target').mkdir()
            (source / 'target' / 'manifest.json').write_text('{}')

            deployment = snow_admin.prepare_dbt_source(root)

            self.assertTrue((deployment / 'env.yml').is_file())
            self.assertFalse((deployment / 'target').exists())

    def run_helper(self, cached=None, code=0, arguments=()):
        vault = Mock()
        vault.get_password.return_value = cached
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snow = root / '.venv/snowflake-cli/Scripts/snow.exe'
            snow.parent.mkdir(parents=True)
            snow.touch()
            observed = {}

            def execute(command, **kwargs):
                observed['command'] = command
                observed['password'] = kwargs['env'].get('SNOWFLAKE_CONNECTIONS_NORTHBRIDGE_ADMIN_PASSWORD')
                observed['environment'] = kwargs['env']
                return Mock(returncode=code)

            with patch.object(snow_admin, 'ROOT', root), \
                    patch.object(snow_admin, 'credential_store', return_value=vault), \
                    patch.object(snow_admin, 'getpass', return_value='test-only-secret') as prompt, \
                    patch.object(snow_admin.subprocess, 'run', side_effect=execute) as run, \
                    patch('sys.argv', ['snow_admin.py', *arguments]), patch('builtins.print'):
                result = snow_admin.main()
            records = list((root / 'data/admin_runs').glob('*.json'))
            for record in records:
                self.assertNotIn('test-only-secret', record.read_text())
                self.assertNotIn('cached-secret', record.read_text())
                self.assertEqual(json.loads(record.read_text())['exit_code'], code)
            if observed:
                self.assertNotIn(observed['password'], observed['command'])
                self.assertNotIn('SNOWFLAKE_CONNECTIONS_NORTHBRIDGE_ADMIN_PASSWORD', observed['environment'])
            return vault, prompt, run, result

    def test_new_password_is_saved_only_after_success(self):
        vault, prompt, _, result = self.run_helper()
        self.assertEqual(result, 0)
        prompt.assert_called_once()
        vault.set_password.assert_called_once_with(snow_admin.SERVICE, snow_admin.USER, 'test-only-secret')
        vault, _, _, _ = self.run_helper(code=1)
        vault.set_password.assert_not_called()

    def test_cached_password_avoids_prompt(self):
        vault, prompt, _, _ = self.run_helper(cached='cached-secret')
        prompt.assert_not_called()
        vault.set_password.assert_not_called()

    def test_refresh_failure_preserves_old_password(self):
        vault, prompt, _, _ = self.run_helper(cached='cached-secret', code=1, arguments=['--refresh-password'])
        prompt.assert_called_once()
        vault.set_password.assert_not_called()
        vault.delete_password.assert_not_called()

    def test_forget_does_not_connect(self):
        vault, prompt, run, _ = self.run_helper(cached='cached-secret', arguments=['--forget-password'])
        vault.delete_password.assert_called_once_with(snow_admin.SERVICE, snow_admin.USER)
        prompt.assert_not_called()
        run.assert_not_called()
