import os
import unittest
from unittest.mock import MagicMock, patch

from scripts.release_dbt import compile_project, record_release, restore_last_release
from pipeline.environment import get_environment


SHA = "a" * 40


class ReleaseRecordTests(unittest.TestCase):
    def test_prod_compile_uses_prod_dates_and_scenario(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (True, None)
        settings = {
            "DBT_BUSINESS_DATE": "2026-10-16",
            "DBT_OPENING_DATE": "2026-10-15",
            "DBT_SCENARIO_ID": "sim-prod-20261016",
        }
        with patch.dict(os.environ, settings):
            compile_project(cursor, get_environment("prod"))
        sql = cursor.execute.call_args.args[0]
        self.assertIn("compile --target prod", sql)
        self.assertIn("'DBT_OPENING_DATE' = '2026-10-15'", sql)
        self.assertIn("'DBT_SCENARIO_ID' = 'sim-prod-20261016'", sql)

    @patch("scripts.release_dbt.snowflake_connection")
    def test_bad_sha_never_connects(self, connect):
        with self.assertRaisesRegex(ValueError, "commit SHA"):
            record_release("dev", "main", "123")
        connect.assert_not_called()

    @patch("scripts.release_dbt.snowflake_connection")
    def test_failed_compile_does_not_record_release(self, connect):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [("NORTHBRIDGE_DBT_DEV",), (False, "compile failed")]
        connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor

        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_DBT_DEV"}):
            with self.assertRaisesRegex(RuntimeError, "compile failed"):
                record_release("dev", SHA, "123")

        sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertFalse(any(text.startswith("INSERT INTO") for text in sql))

    @patch("scripts.release_dbt.snowflake_connection")
    def test_restore_uses_the_last_good_source(self, connect):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("COMMIT_SHA",), ("CI_RUN_ID",)]
        cursor.fetchone.side_effect = [
            ("NORTHBRIDGE_DBT_DEV",), (SHA, 123), (True, None)
        ]
        connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor

        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_DBT_DEV"}):
            restore_last_release("dev")

        sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertIn("ALTER DBT PROJECT NORTHBRIDGE_DEV.DBT_DEV.NORTHBRIDGE_DAILY "
                      "DEPLOY FROM '@NORTHBRIDGE_DEV.DBT_DEV.DBT_SOURCE/project/'", sql)
        self.assertTrue(any("'RESTORE'" in text for text in sql))

    @patch("scripts.release_dbt.snowflake_connection")
    def test_restore_uses_the_recorded_commit_folder(self, connect):
        cursor = MagicMock()
        source = "@NORTHBRIDGE_DEV.DBT_DEV.DBT_SOURCE/commits/{}/".format(SHA)
        cursor.fetchall.return_value = [("COMMIT_SHA",), ("STAGE_PATH",)]
        cursor.fetchone.side_effect = [
            ("NORTHBRIDGE_DBT_DEV",), (SHA, 123, source), (True, None)
        ]
        connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor

        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_DBT_DEV"}):
            restore_last_release("dev")

        sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertIn("ALTER DBT PROJECT NORTHBRIDGE_DEV.DBT_DEV.NORTHBRIDGE_DAILY "
                      "DEPLOY FROM '{}'".format(source), sql)


if __name__ == "__main__":
    unittest.main()
