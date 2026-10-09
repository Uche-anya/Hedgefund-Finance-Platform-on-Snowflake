import unittest
from pathlib import Path
from unittest.mock import Mock

from pipeline.recover_file import recover


class RecoveryGuardTests(unittest.TestCase):
    def test_existing_raw_rows_stop_manual_copy(self):
        item = {
            "source": "oms",
            "date": "2024-09-24",
            "scenario": "test",
            "rows": 4,
            "sha256": "abc",
            "path": "oms/business_date=2024-09-24/delivery_id=test-1/oms.jsonl",
            "id": "test-1",
            "file": Path("unused.jsonl"),
        }
        cursor = Mock()
        cursor.fetchone.side_effect = [
            ("oms", "2024-09-24", "test", 4, "abc", item["path"], "SUBMITTED"),
            (2,),
        ]
        with self.assertRaisesRegex(ValueError, "RAW already contains rows"):
            recover(cursor, item)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertFalse(any(sql.startswith("COPY INTO") for sql in statements))


if __name__ == "__main__":
    unittest.main()
