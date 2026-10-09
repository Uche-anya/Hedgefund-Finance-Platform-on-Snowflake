import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pipeline.load_day import stage_has_file, submit


class DeliveryRetryTests(unittest.TestCase):
    def setUp(self):
        self.item = {
            "source": "oms",
            "date": "2024-09-25",
            "scenario": "test-scenario",
            "rows": 4,
            "sha256": "abc123",
            "path": "oms/business_date=2024-09-25/delivery_id=test-1/oms.jsonl",
            "id": "test-1",
            "file": Path("unused.jsonl"),
        }

    def test_submitted_delivery_is_not_sent_again(self):
        cursor = Mock()
        cursor.fetchone.return_value = (
            "oms", "2024-09-25", "test-scenario", 4, "abc123",
            self.item["path"], "SUBMITTED"
        )
        with patch("pipeline.load_day.request_snowpipe") as send:
            submit(cursor, self.item)
        self.assertEqual(cursor.execute.call_count, 1)
        send.assert_not_called()

    def test_changed_file_cannot_reuse_delivery_id(self):
        cursor = Mock()
        cursor.fetchone.return_value = (
            "oms", "2024-09-25", "test-scenario", 4, "different-hash",
            self.item["path"], "SUBMITTED"
        )
        with self.assertRaisesRegex(ValueError, "different content"):
            submit(cursor, self.item)

    def test_new_file_is_staged_once_then_submitted(self):
        cursor = Mock()
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = []
        with patch("pipeline.load_day.request_snowpipe") as send:
            submit(cursor, self.item)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        put = next(sql for sql in statements if sql.startswith("PUT "))
        self.assertIn("@NORTHBRIDGE_DEV.RAW.DAILY_LANDING/oms/business_date=2024-09-25/"
                      "delivery_id=test-1/'", put)
        self.assertNotIn("oms.jsonl/oms.jsonl", put)
        self.assertTrue(any("status = 'SUBMITTED'" in sql for sql in statements))
        send.assert_called_once_with(self.item)

    def test_unregistered_stage_file_is_not_submitted(self):
        cursor = Mock()
        cursor.fetchone.return_value = None
        cursor.fetchall.return_value = [("daily_landing/" + self.item["path"],)]
        with patch("pipeline.load_day.request_snowpipe") as send:
            with self.assertRaisesRegex(ValueError, "without a registry entry"):
                submit(cursor, self.item)
        send.assert_not_called()

    def test_stage_prefix_does_not_count_a_nested_file(self):
        cursor = Mock()
        cursor.fetchall.return_value = [
            ("daily_landing/" + self.item["path"] + "/oms.jsonl",)
        ]
        self.assertFalse(stage_has_file(cursor, "@stage/" + self.item["path"],
                                        self.item["path"]))

    def test_empty_delivery_does_not_call_snowpipe(self):
        cursor = Mock()
        cursor.fetchone.return_value = None
        self.item["rows"] = 0
        with patch("pipeline.load_day.request_snowpipe") as send:
            submit(cursor, self.item)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("status = 'EMPTY'" in sql for sql in statements))
        self.assertFalse(any(sql.startswith("PUT ") for sql in statements))
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
