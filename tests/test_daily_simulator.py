import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from pipeline.daily_simulator import next_weekday, previous_weekday, prior_close, write_day


class DailySimulatorTest(unittest.TestCase):
    def test_friday_trades_settle_after_weekend_and_retry_matches(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            closes = {"AAPL": Decimal("245"), "AMZN": Decimal("227"),
                      "MSFT": Decimal("420"), "KO": Decimal("65")}
            due = [("SIM-EXEC-20261008-01", "SIM-ACCOUNT-01", "AAPL.US",
                    "BUY", "10", "244.00", "2026-10-09"),
                   ("SIM-EXEC-20261008-02", "SIM-ACCOUNT-01", "AMZN.US",
                    "SELL", "5", "227.00", "2026-10-09")]
            args = ("2026-10-09", "demo", folder, "2026-10-08", closes, due)
            self.assertEqual(write_day(*args), (4, 2))
            self.assertEqual(write_day(*args), (4, 2))
            oms_file = folder / "daily_oms/demo/2026-10-09/oms.jsonl"
            settlement_file = folder / "daily_settlements/demo/2026-10-09/settlements.jsonl"
            trades = [json.loads(line) for line in oms_file.read_text().splitlines()]
            settled = [json.loads(line) for line in settlement_file.read_text().splitlines()]
            self.assertEqual({row["settlement_due"] for row in trades}, {"2026-10-12"})
            self.assertEqual([row["cash_amount"] for row in settled],
                             ["-2440.00", "1135.00"])
            self.assertTrue(all(row["is_simulated"] for row in trades + settled))

    def test_next_weekday(self):
        self.assertEqual(next_weekday(date(2026, 10, 9)), date(2026, 10, 12))
        self.assertEqual(previous_weekday(date(2026, 10, 12)), date(2026, 10, 9))

    def test_missing_prior_weekday_stops_new_close(self):
        cursor = Mock()
        cursor.fetchone.return_value = (date(2026, 10, 8),)
        with self.assertRaisesRegex(ValueError, "recover that date first"):
            prior_close(cursor, "2026-10-12", "demo")


if __name__ == "__main__":
    unittest.main()
