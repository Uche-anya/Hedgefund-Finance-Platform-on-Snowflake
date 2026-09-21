import copy
from datetime import date
from pathlib import Path
import tempfile
import unittest

from business_calendar import next_close_date, validate_close_dates
from carry_cash import roll_cash


class BusinessCalendarTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "daily_cash" / "2025-01-10"
        for name in ("executions.csv", "allocations.csv", "execution_terms.csv", "settlements.csv"):
            (self.folder / name).write_text((fixtures / name).read_text().splitlines()[0] + "\n")
        self.opening = {"currency": "USD", "cash": "1000.00", "payables": "720.00", "receivables": "50.00",
            "known_execution_ids": ["OLD-BUY", "OLD-SELL"], "obligations": [
                {"execution_id": "OLD-BUY", "type": "PAYABLE", "amount": "720.00", "due": "2025-01-11"},
                {"execution_id": "OLD-SELL", "type": "RECEIVABLE", "amount": "50.00", "due": "2025-01-12"}]}

    def settlements(self, rows):
        path = self.folder / "settlements.csv"
        path.write_text(path.read_text().splitlines()[0] + "\n" + rows)

    def test_friday_to_monday_and_regular_weekday(self):
        self.assertEqual(next_close_date(date(2025, 1, 10)), date(2025, 1, 13))
        self.assertEqual(validate_close_dates("2025-01-10", "2025-01-13")[1], date(2025, 1, 13))
        validate_close_dates("2025-01-09", "2025-01-10")

    def test_weekend_closes_and_skipped_weekdays_are_rejected(self):
        for previous, today in (("2025-01-10", "2025-01-11"), ("2025-01-10", "2025-01-14"),
                                 ("2025-01-09", "2025-01-13"), ("2025-01-12", "2025-01-13")):
            with self.subTest(previous=previous, today=today):
                with self.assertRaisesRegex(ValueError, "next weekday"):
                    validate_close_dates(previous, today)

    def test_weekend_settlements_preserve_actual_dates_and_do_not_double_count(self):
        saturday = "2025-01-13,S1,OLD-BUY,USD,720.00,2025-01-11\n"
        sunday = "2025-01-13,S2,OLD-SELL,USD,50.00,2025-01-12\n"
        self.settlements(saturday + saturday + sunday)
        untouched = copy.deepcopy(self.opening)
        result = roll_cash(self.opening, self.folder, "2025-01-10", "2025-01-13")
        self.assertEqual(result["cash"], 330)
        self.assertEqual(result["obligations"], [])
        self.assertEqual(result["repeated_settlements"], 1)
        self.assertEqual([row["settled_on"] for row in result["cash_movements"]], ["2025-01-11", "2025-01-12"])
        self.assertEqual(result, roll_cash(self.opening, self.folder, "2025-01-10", "2025-01-13"))
        self.assertEqual(self.opening, untouched)

    def test_no_confirmation_leaves_weekend_due_obligations_overdue(self):
        result = roll_cash(self.opening, self.folder, "2025-01-10", "2025-01-13")
        self.assertEqual(result["cash"], 1000)
        self.assertEqual(result["payables"], 720)
        self.assertEqual(result["receivables"], 50)
        self.assertTrue(all(row["status"] == "OVERDUE" for row in result["obligations"]))

    def test_settlement_outside_opening_to_close_window_is_rejected(self):
        for settled in ("2025-01-10", "2025-01-09", "2025-01-14"):
            with self.subTest(settled=settled):
                self.settlements(f"2025-01-13,S1,OLD-BUY,USD,720.00,{settled}\n")
                with self.assertRaisesRegex(ValueError, "after the opening close"):
                    roll_cash(self.opening, self.folder, "2025-01-10", "2025-01-13")

    def test_new_monday_trade_cannot_settle_on_saturday(self):
        rows = {"executions.csv": "2025-01-13,NEW,AAPL.US,BUY,1\n",
                "allocations.csv": "2025-01-13,A1,NEW,GROWTH,1\n",
                "execution_terms.csv": "2025-01-13,NEW,USD,250.00,2025-01-14\n"}
        for name, row in rows.items():
            with (self.folder / name).open("a") as file:
                file.write(row)
        self.settlements("2025-01-13,S3,NEW,USD,250.00,2025-01-11\n")
        with self.assertRaisesRegex(ValueError, "precede today's new trade"):
            roll_cash(self.opening, self.folder, "2025-01-10", "2025-01-13")


if __name__ == "__main__":
    unittest.main()
