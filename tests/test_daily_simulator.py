import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from pipeline.daily_simulator import prior_close, unsettled_trades, write_day
from pipeline.us_equity_calendar import (
    is_market_day, is_settlement_day, next_settlement_day, previous_market_day
)


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
            self.assertEqual({row["settlement_due"] for row in trades}, {"2026-10-13"})
            self.assertEqual([row["cash_amount"] for row in settled],
                             ["-2440.00", "1135.00"])
            self.assertTrue(all(row["is_simulated"] for row in trades + settled))

    def test_trading_day_can_be_a_settlement_holiday(self):
        self.assertTrue(is_market_day(date(2026, 10, 12)))
        self.assertFalse(is_settlement_day(date(2026, 10, 12)))
        self.assertEqual(next_settlement_day(date(2026, 10, 9)), date(2026, 10, 13))
        self.assertEqual(previous_market_day(date(2026, 10, 12)), date(2026, 10, 9))
        cursor = Mock()
        self.assertEqual(unsettled_trades(cursor, "2026-10-12", "demo"), [])
        cursor.execute.assert_not_called()

    def test_unreviewed_calendar_year_stops(self):
        with self.assertRaisesRegex(ValueError, "No reviewed US equity calendar"):
            is_market_day(date(2027, 1, 4))

    def test_bank_holiday_has_trades_but_no_settlements(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            closes = {"AAPL": Decimal("245"), "AMZN": Decimal("227"),
                      "MSFT": Decimal("420"), "KO": Decimal("65")}
            self.assertEqual(write_day("2026-10-12", "demo", folder,
                                       "2026-10-09", closes, []), (4, 0))
            events = folder / "daily_settlements/demo/2026-10-12/settlements.jsonl"
            self.assertEqual(events.read_text(), "")
            with self.assertRaisesRegex(ValueError, "settlement holiday"):
                write_day("2026-10-12", "demo", folder,
                          "2026-10-09", closes, [("x", "a", "AAPL.US", "BUY", "1", "1", "2026-10-12")])

    def test_missing_prior_weekday_stops_new_close(self):
        cursor = Mock()
        cursor.fetchone.return_value = (date(2026, 10, 8),)
        with self.assertRaisesRegex(ValueError, "recover that date first"):
            prior_close(cursor, "2026-10-12", "demo")


if __name__ == "__main__":
    unittest.main()
