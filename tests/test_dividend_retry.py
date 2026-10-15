"""Do not replace a dated Massive snapshot just because a retry saw new data."""

import unittest
from unittest.mock import MagicMock

from pipeline.dividends import submit


class DividendRetryTest(unittest.TestCase):
    def test_changed_snapshot_stops_before_loading(self):
        cursor = MagicMock()
        cursor.fetchall.return_value = [("earlier-delivery",)]
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            submit(cursor, {"id": "new-delivery", "date": "2026-10-13"})
        self.assertEqual(cursor.execute.call_count, 1)


if __name__ == "__main__":
    unittest.main()
