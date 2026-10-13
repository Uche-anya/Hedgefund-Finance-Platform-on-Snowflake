"""The deadline check must not mistake missing or duplicate runs for success."""

import unittest

from pipeline.check_close_deadline import check_close


class Cursor:
    def __init__(self, statuses):
        self.statuses = statuses
        self.params = None

    def execute(self, query, params):
        self.params = params

    def fetchall(self):
        return [(status,) for status in self.statuses]


class CloseDeadlineTest(unittest.TestCase):
    def test_one_validated_close(self):
        cursor = Cursor(["FAILED", "VALIDATED"])
        check_close(cursor, "2026-10-12", "demo")
        self.assertEqual(cursor.params, ("2026-10-12", "demo"))

    def test_missing_close_fails(self):
        for statuses in ([], ["FAILED"], ["VALIDATED", "VALIDATED"]):
            with self.subTest(statuses=statuses):
                with self.assertRaises(RuntimeError):
                    check_close(Cursor(statuses), "2026-10-12", "demo")


if __name__ == "__main__":
    unittest.main()
