import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from data_extraction.check_ticker_changes import PAIRS, compare_pair, run_checks


def identity(exchange="XNYS"):
    return {"name": "Fictional issuer", "cik": "000123", "share_class_figi": "TEST-SHARE",
            "composite_figi": "TEST-COMPOSITE", "type": "CS", "currency_name": "usd",
            "primary_exchange": exchange, "active": True}


class TickerChangeTests(unittest.TestCase):
    def test_expected_exchange_transfer_and_cik_padding_are_allowed(self):
        old = identity()
        new = identity("XNAS")
        new["cik"] = "123"
        new["name"] = "Renamed fictional issuer"
        status, _ = compare_pair(old, new, "XNYS", "XNAS")
        self.assertEqual(status, "IDENTIFIERS_MATCH")

    def test_missing_identifiers_never_count_as_matches(self):
        for value in (None, "", "  "):
            with self.subTest(value=value):
                old, new = identity(), identity()
                old["share_class_figi"] = new["share_class_figi"] = value
                self.assertEqual(compare_pair(old, new, "XNYS", "XNYS")[0], "REVIEW_MISSING")

    def test_conflicting_identifier_exchange_or_type_requires_review(self):
        for field, value in (("share_class_figi", "OTHER"), ("primary_exchange", "XNAS"),
                             ("type", "FUND"), ("active", False)):
            with self.subTest(field=field):
                old, new = identity(), identity()
                new[field] = value
                self.assertEqual(compare_pair(old, new, "XNYS", "XNYS")[0], "REVIEW_CONFLICT")

    def test_eight_dated_requests_write_four_comparisons(self):
        payloads = []
        expected_calls = []
        for old, new, old_day, new_day, old_exchange, new_exchange in PAIRS:
            for ticker, day, exchange in ((old, old_day, old_exchange), (new, new_day, new_exchange)):
                payloads.append(json.dumps({"status": "OK", "results": {
                    **identity(exchange), "ticker": ticker}}).encode())
                expected_calls.append((ticker, day, "test-key"))
        with tempfile.TemporaryDirectory() as temp:
            with patch("data_extraction.check_bny_identity.fetch_details", side_effect=payloads) as fetch, \
                    patch("data_extraction.check_bny_identity.time.sleep") as sleep, patch("builtins.print"):
                folder = run_checks(Path(temp), "test-key")
            self.assertEqual([call.args for call in fetch.call_args_list], expected_calls)
            self.assertEqual(sleep.call_count, 7)
            with (folder / "comparisons.csv").open(newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 4)
            self.assertTrue(all(row["status"] == "IDENTIFIERS_MATCH" for row in rows))
