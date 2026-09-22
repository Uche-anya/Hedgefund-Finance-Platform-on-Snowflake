from datetime import datetime
import json
import unittest

from repair_xyz_history import combine_prices


def prices(ticker, dates, close):
    bars = []
    for day in dates:
        timestamp = int(datetime.fromisoformat(day + "T00:00:00-05:00").timestamp() * 1000)
        bars.append({"t": timestamp, "o": close, "h": close, "l": close, "c": close, "v": 100})
    return json.dumps({"status": "OK", "ticker": ticker, "adjusted": False,
                       "resultsCount": len(bars), "results": bars}).encode()


class BlockRepairTests(unittest.TestCase):
    def test_joins_at_change_date_without_filling_nontrading_days(self):
        rows = combine_prices(
            prices("SQ", ["2025-01-16", "2025-01-17"], 90),
            prices("XYZ", ["2025-01-17", "2025-01-21"], 91),
            prices("AAPL", ["2025-01-16", "2025-01-17", "2025-01-21"], 200),
            "2025-01-16", "2025-01-21",
        )
        self.assertEqual([r["source_ticker"] for r in rows], ["SQ", "SQ", "XYZ"])
        self.assertEqual(rows[1]["close_price"], "90")
        self.assertEqual(len({r["instrument_id"] for r in rows}), 1)
        self.assertEqual([r["valuation_date"] for r in rows], ["2025-01-16", "2025-01-17", "2025-01-21"])

    def test_missing_day_stops_the_repair(self):
        with self.assertRaisesRegex(ValueError, "Missing"):
            combine_prices(prices("SQ", ["2025-01-16"], 90),
                           prices("XYZ", ["2025-01-21"], 91),
                           prices("AAPL", ["2025-01-16", "2025-01-17", "2025-01-21"], 200),
                           "2025-01-16", "2025-01-21")

    def test_duplicate_dates_and_sq_after_change_are_rejected(self):
        for dates in (["2025-01-17", "2025-01-17"], ["2025-01-17", "2025-01-21"]):
            with self.subTest(dates=dates), self.assertRaises(ValueError):
                combine_prices(prices("SQ", dates, 90),
                               prices("XYZ", ["2025-01-21"], 91),
                               prices("AAPL", ["2025-01-17", "2025-01-21"], 200),
                               "2025-01-17", "2025-01-21")
