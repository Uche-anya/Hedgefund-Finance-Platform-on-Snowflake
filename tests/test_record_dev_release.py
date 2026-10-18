import os
import unittest
from unittest.mock import MagicMock, patch

from scripts.release_dbt import record_release, restore_last_release


SHA = "a" * 40


class ReleaseRecordTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
