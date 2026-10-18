import os
import unittest
from unittest.mock import MagicMock, patch

from scripts.record_dev_release import record_release


SHA = "a" * 40


class ReleaseRecordTests(unittest.TestCase):
    @patch("scripts.record_dev_release.snowflake_connection")
    def test_bad_sha_never_connects(self, connect):
        with self.assertRaisesRegex(ValueError, "commit SHA"):
            record_release("main", "123")
        connect.assert_not_called()

    @patch("scripts.record_dev_release.snowflake_connection")
    def test_failed_compile_does_not_record_release(self, connect):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [("NORTHBRIDGE_DBT_DEV",), (False, "compile failed")]
        connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = cursor

        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_DBT_DEV"}):
            with self.assertRaisesRegex(RuntimeError, "compile failed"):
                record_release(SHA, "123")

        sql = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertFalse(any(text.startswith("INSERT INTO") for text in sql))


if __name__ == "__main__":
    unittest.main()
