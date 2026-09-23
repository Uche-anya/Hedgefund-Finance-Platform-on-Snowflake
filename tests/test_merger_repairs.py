import unittest

from data_extraction.repair_merger_histories import IDENTITIES, PAIRS, approve_identity, combine_prices
from test_ticker_repairs import prices


def identity(ticker, exchange):
    _, share, composite, cik = IDENTITIES[ticker]
    return dict(cik=cik, share_class_figi=share, composite_figi=composite,
                type="CS", primary_exchange=exchange, currency_name="usd", active=True)


class MergerRepairTests(unittest.TestCase):
    def test_exe_missing_cik_exception_is_narrow(self):
        old, new = identity("EXE", "XNAS"), identity("EXE", "XNAS")
        new["cik"] = ""
        self.assertIn("Chesapeake", approve_identity(PAIRS[0], old, new))
        self.assertEqual(new["cik"], "")
        for field, value in (("cik", "123"), ("share_class_figi", ""),
                             ("primary_exchange", "XNYS"), ("active", False)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                approve_identity(PAIRS[0], old, {**new, field: value})

    def test_vmrk_requires_complete_matching_identifiers(self):
        old, new = identity("VMRK", "XNYS"), identity("VMRK", "XNYS")
        approve_identity(PAIRS[1], old, new)
        new["cik"] = ""
        with self.assertRaises(ValueError):
            approve_identity(PAIRS[1], old, new)

    def test_both_boundaries_keep_old_prices_until_change(self):
        for pair in PAIRS:
            old, new, before, after, _, _ = pair
            with self.subTest(ticker=new):
                rows = combine_prices(pair, prices(old, [before], 50),
                                      prices(new, [before, after], 51),
                                      prices("AAPL", [before, after], 200), before, after)
                self.assertEqual([r["source_ticker"] for r in rows], [old, new])
                self.assertEqual(rows[0]["close_price"], "50")
                self.assertEqual(rows[0]["instrument_id"], rows[1]["instrument_id"])

    def test_gap_or_duplicate_stops_repair(self):
        for dates in (["2024-09-30"], ["2024-09-30", "2024-09-30"]):
            with self.subTest(dates=dates), self.assertRaises(ValueError):
                combine_prices(PAIRS[0], prices("CHK", dates, 50),
                               prices("EXE", ["2024-10-02"], 51),
                               prices("AAPL", ["2024-09-30", "2024-10-01", "2024-10-02"], 200),
                               "2024-09-30", "2024-10-02")
