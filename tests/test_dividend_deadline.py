"""The deadline check must distinguish a complete delivery from a missing one."""

import unittest

from pipeline.check_dividend_deadline import check_dividends


class Cursor:
    def __init__(self, rows):
        self.rows = rows
        self.params = None

    def execute(self, query, params):
        self.params = params

    def fetchall(self):
        return self.rows


class DividendDeadlineTest(unittest.TestCase):
    def test_latest_complete_delivery_passes(self):
        cursor = Cursor([("new", 3, "LOADED", 3), ("old", 3, "LOADED", 3)])
        check_dividends(cursor, "2026-10-13")
        self.assertEqual(cursor.params, ("2026-10-13",))

    def test_missing_or_incomplete_latest_delivery_fails(self):
        cases = ([], [("new", 3, "PREPARED", 0), ("old", 3, "LOADED", 3)],
                 [("new", 3, "LOADED", 2)], [("new", 0, "EMPTY", 1)])
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                check_dividends(Cursor(rows), "2026-10-13")

    def test_empty_market_snapshot_fails(self):
        with self.assertRaises(RuntimeError):
            check_dividends(Cursor([("empty", 0, "EMPTY", 0)]), "2026-10-13")


if __name__ == "__main__":
    unittest.main()
