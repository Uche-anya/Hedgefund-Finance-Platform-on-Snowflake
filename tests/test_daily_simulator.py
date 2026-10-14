import json
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

from pipeline.daily_simulator import (ORDER_BOOK, prior_close, prior_prices,
                                      trades_for_day, unsettled_trades, write_day)
from pipeline.us_equity_calendar import (
    is_market_day, is_settlement_day, next_settlement_day, previous_market_day
)


class DailySimulatorTest(unittest.TestCase):
    def test_expanded_book_starts_after_october_13(self):
        self.assertEqual(len(trades_for_day(date(2026, 10, 13))), 4)
        first = trades_for_day(date(2026, 10, 14))
        self.assertEqual(len(first), 8)
        self.assertEqual({row[0] for row in first}, set(ORDER_BOOK))
        traded = set()
        for day in (14, 15, 16):
            traded.update(row[1] for row in trades_for_day(date(2026, 10, day)))
        self.assertEqual(len(traded), 20)

    def test_expanded_day_is_reproducible_and_needs_prior_prices(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            closes = {row[1]: Decimal("100") for row in
                      trades_for_day(date(2026, 10, 14))}
            args = ("2026-10-14", "demo", folder, "2026-10-13", closes, [])
            self.assertEqual(write_day(*args), (8, 0))
            self.assertEqual(write_day(*args), (8, 0))
            path = folder / "daily_oms/demo/2026-10-14/oms.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len({row["execution_id"] for row in rows}), 8)
            self.assertEqual({row["settlement_due"] for row in rows}, {"2026-10-15"})
            self.assertTrue(all(row["is_simulated"] for row in rows))
            self.assertEqual({row["simulator_plan_id"] for row in rows},
                             {"equity_20_20261014"})
            with self.assertRaisesRegex(ValueError, "Previous close missing"):
                write_day("2026-10-15", "other", folder, "2026-10-14", closes, [])

    def test_previous_price_query_uses_the_new_day_plan(self):
        cursor = Mock()
        tickers = sorted({row[1] for row in trades_for_day(date(2026, 10, 14))})
        cursor.fetchall.return_value = [(ticker, Decimal("100")) for ticker in tickers]
        self.assertEqual(len(prior_prices(cursor, "2026-10-13", "2026-10-14")), 8)
        self.assertEqual(cursor.execute.call_args.args[1], ("2026-10-13",) + tuple(tickers))

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
