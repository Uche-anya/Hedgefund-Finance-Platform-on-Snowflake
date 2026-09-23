from datetime import datetime
import json
import unittest

from data_extraction.repair_ticker_changes import IDENTITIES, PAIRS, approve_identity, combine_prices


def identity(new, exchange):
    _, figi, composite, cik = IDENTITIES[new]
    return {"cik": cik, "share_class_figi": figi, "composite_figi": composite,
            "type": "CS", "primary_exchange": exchange, "currency_name": "usd", "active": True}


def prices(ticker, dates, price):
    bars = []
    for day in dates:
        timestamp = int(datetime.fromisoformat(day + "T00:00:00-04:00").timestamp() * 1000)
        bars.append({"t": timestamp, "o": price, "h": price, "l": price, "c": price, "v": 100})
    return json.dumps({"status": "OK", "ticker": ticker, "adjusted": False,
                       "resultsCount": len(bars), "results": bars}).encode()


class TickerRepairTests(unittest.TestCase):
    def test_fiserv_exception_keeps_missing_cik_and_records_reason(self):
        pair = PAIRS[2]
        old, new = identity("FISV", "XNYS"), identity("FISV", "XNAS")
        new["cik"] = ""
        reason = approve_identity(pair, old, new)
        self.assertIn("337738108", reason)
        self.assertEqual(new["cik"], "")

    def test_fiserv_exception_does_not_allow_conflicts_or_other_missing_fields(self):
        for field, value in (("cik", "999"), ("share_class_figi", ""),
                             ("primary_exchange", "XNYS"), ("active", False)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                old, new = identity("FISV", "XNYS"), identity("FISV", "XNAS")
                new["cik"] = ""
                new[field] = value
                approve_identity(PAIRS[2], old, new)

    def test_missing_cik_is_not_accepted_for_other_pairs(self):
        old, new = identity("ECHO", "XNAS"), identity("ECHO", "XNAS")
        new["cik"] = ""
        with self.assertRaises(ValueError):
            approve_identity(PAIRS[0], old, new)

    def test_date_boundary_excludes_prechange_new_symbol(self):
        pair = PAIRS[0]
        rows = combine_prices(pair, prices("SATS", ["2026-06-22", "2026-06-23"], 50),
                              prices("ECHO", ["2026-06-23", "2026-06-24"], 51),
                              prices("AAPL", ["2026-06-22", "2026-06-23", "2026-06-24"], 200),
                              "2026-06-22", "2026-06-24")
        self.assertEqual([r["source_ticker"] for r in rows], ["SATS", "SATS", "ECHO"])
        self.assertEqual(rows[1]["close_price"], "50")

    def test_gaps_and_duplicate_dates_stop_repair(self):
        for dates in (["2026-06-22"], ["2026-06-22", "2026-06-22"]):
            with self.subTest(dates=dates), self.assertRaises(ValueError):
                combine_prices(PAIRS[0], prices("SATS", dates, 50),
                               prices("ECHO", ["2026-06-24"], 51),
                               prices("AAPL", ["2026-06-22", "2026-06-23", "2026-06-24"], 200),
                               "2026-06-22", "2026-06-24")
