import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from check_bny_identity import CHECKS, check_identities, read_identity


def response(ticker):
    return json.dumps({"status": "OK", "results": {
        "ticker": ticker, "name": "Fictional test issuer", "cik": "123",
        "share_class_figi": "TEST-ONLY", "active": True,
    }}).encode()


class IdentityTests(unittest.TestCase):
    def test_saves_all_dated_responses_and_preserves_missing_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("check_bny_identity.fetch_details", side_effect=[response(t) for t, d in CHECKS]) as fetch, \
                    patch("check_bny_identity.time.sleep"), patch("builtins.print"):
                folder = check_identities(Path(temp), "test-secret")
            self.assertEqual([call.args[:2] for call in fetch.call_args_list], list(CHECKS))
            with (folder / "identities.csv").open(newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0]["composite_figi"], "")
            self.assertEqual((folder / "BNY_2026-02-06.json").read_bytes(), response("BNY"))
            self.assertNotIn("test-secret", (folder / "manifest.json").read_text())

    def test_wrong_ticker_and_provider_error_are_rejected(self):
        for payload in (response("OTHER"), b'{"status":"ERROR"}', b'{"status":"OK","results":{}}'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                read_identity(payload, "BK", "2026-05-20")

    def test_failed_request_does_not_create_completion_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("check_bny_identity.fetch_details", side_effect=RuntimeError("HTTP 403")), \
                    patch("builtins.print"), self.assertRaises(RuntimeError):
                check_identities(Path(temp), "test-secret")
            self.assertEqual(list(Path(temp).glob("*/manifest.json")), [])
