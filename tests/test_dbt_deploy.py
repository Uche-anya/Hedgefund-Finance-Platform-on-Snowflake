import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.deploy_dbt_project import REQUIRED_RAW_TABLES, deploy


class DeployChecks(unittest.TestCase):
    @patch("scripts.deploy_dbt_project.snowflake_connection")
    def test_wrong_role_never_connects(self, connect):
        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_DBT_DEV"}):
            with self.assertRaisesRegex(ValueError, "requires role"):
                deploy(Path("dbt"), "prod")
        connect.assert_not_called()

    @patch("scripts.deploy_dbt_project.snowflake_connection")
    def test_missing_raw_tables_stop_before_upload(self, connect):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("NORTHBRIDGE_DBT_PROD",)
        cursor.fetchall.return_value = []
        connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor

        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_DBT_PROD"}):
            with self.assertRaisesRegex(ValueError, "RAW is missing"):
                deploy(Path("dbt"), "prod")

        sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertFalse(any(text.startswith("CREATE STAGE") or text.startswith("PUT ")
                             for text in sql))

    @patch("scripts.deploy_dbt_project.project_files", return_value=[Path("dbt/dbt_project.yml")])
    @patch("scripts.deploy_dbt_project.snowflake_connection")
    def test_release_upload_uses_commit_folder(self, connect, _):
        sha = "a" * 40
        cursor = MagicMock()
        cursor.fetchone.return_value = ("NORTHBRIDGE_DBT_TEST",)
        cursor.fetchall.side_effect = [
            [(name,) for name in REQUIRED_RAW_TABLES],
            [(None, "NORTHBRIDGE_DAILY")],
        ]
        connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor
        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_DBT_TEST"}):
            deploy(Path("dbt"), "test", sha)
        sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("/commits/{}/".format(sha) in text and
                            "OVERWRITE = FALSE" in text for text in sql if text.startswith("PUT ")))
        self.assertTrue(any("DEPLOY FROM '@NORTHBRIDGE_TEST.DBT_TEST.DBT_SOURCE/commits/{}/'".format(sha)
                            in text for text in sql))


if __name__ == "__main__":
    unittest.main()
