from datetime import datetime
import json
import unittest

from data_extraction.repair_bny_history import combine_prices


def prices(ticker, dates, price):
    bars = []
    for day in dates:
        timestamp = int(datetime.fromisoformat(day + "T00:00:00-04:00").timestamp() * 1000)
        bars.append({"t": timestamp, "o": price, "h": price, "l": price, "c": price, "v": 100})
    return json.dumps({"status": "OK", "ticker": ticker, "adjusted": False,
                       "resultsCount": len(bars), "results": bars}).encode()


class BankRepairTests(unittest.TestCase):
    def test_reused_ticker_prices_are_excluded_and_bank_identity_is_stable(self):
        bk = prices("BK", ["2026-05-19", "2026-05-20"], 130)
        bny = prices("BNY", ["2026-05-19", "2026-05-21"], 10)
        peer = prices("AAPL", ["2026-05-19", "2026-05-20", "2026-05-21"], 200)
        rows = combine_prices(bk, bny, peer, "2026-05-19", "2026-05-21")
        self.assertEqual([r["source_ticker"] for r in rows], ["BK", "BK", "BNY"])
        self.assertEqual(rows[0]["close_price"], "130")
        self.assertEqual(len({r["instrument_id"] for r in rows}), 1)

    def test_missing_bank_date_stops_repair(self):
        with self.assertRaisesRegex(ValueError, "Missing"):
            combine_prices(prices("BK", ["2026-05-19"], 130),
                           prices("BNY", ["2026-05-21"], 131),
                           prices("AAPL", ["2026-05-19", "2026-05-20", "2026-05-21"], 200),
                           "2026-05-19", "2026-05-21")

    def test_bk_after_change_and_duplicate_dates_are_rejected(self):
        for dates in (["2026-05-20", "2026-05-21"], ["2026-05-20", "2026-05-20"]):
            with self.subTest(dates=dates), self.assertRaises(ValueError):
                combine_prices(prices("BK", dates, 130),
                               prices("BNY", ["2026-05-21"], 131),
                               prices("AAPL", ["2026-05-20", "2026-05-21"], 200),
                               "2026-05-20", "2026-05-21")
