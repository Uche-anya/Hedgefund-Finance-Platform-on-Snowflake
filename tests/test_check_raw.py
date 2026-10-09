import unittest
from unittest.mock import Mock

from pipeline.check_raw import check_held_prices, check_source


class RawReadinessTests(unittest.TestCase):
    def test_empty_settlement_delivery_is_ready(self):
        cursor = Mock()
        cursor.fetchall.return_value = [("empty-1", 0, "settlements/day/file", "EMPTY")]
        cursor.fetchone.return_value = (0,)
        ready, message = check_source(cursor, "2024-09-24", "test", "settlements")
        self.assertTrue(ready)
        self.assertIn("empty delivery", message)

    def test_submitted_file_waits_for_all_rows(self):
        cursor = Mock()
        cursor.fetchall.return_value = [("oms-1", 4, "oms/day/file", "SUBMITTED")]
        cursor.fetchone.return_value = (3,)
        ready, message = check_source(cursor, "2024-09-25", "test", "oms")
        self.assertFalse(ready)
        self.assertIn("3 of 4", message)

    def test_two_registry_rows_are_not_ready(self):
        cursor = Mock()
        cursor.fetchall.return_value = [
            ("oms-1", 4, "oms/day/file", "SUBMITTED"),
            ("oms-1", 4, "oms/day/file", "SUBMITTED"),
        ]
        ready, message = check_source(cursor, "2024-09-25", "test", "oms")
        self.assertFalse(ready)
        self.assertIn("found 2", message)

    def test_held_stock_without_close_stops_run(self):
        cursor = Mock()
        cursor.fetchall.side_effect = [[("prices/day/file",)], [("AMZN",)]]
        cursor.fetchone.return_value = (2, 2, 0)
        ready, message = check_held_prices(cursor, "2024-09-25", "test")
        self.assertFalse(ready)
        self.assertIn("AMZN", message)


if __name__ == "__main__":
    unittest.main()
