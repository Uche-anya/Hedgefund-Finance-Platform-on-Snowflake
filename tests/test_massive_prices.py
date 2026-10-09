import csv
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.massive_prices import fetch, price_rows, read_api_key
from pipeline.prices import prepare


class MassivePriceTests(unittest.TestCase):
    def response(self):
        return {
            "status": "OK",
            "adjusted": False,
            "request_id": "provider-123",
            "resultsCount": 2,
            "results": [{"T": "AAPL", "c": 226.37},
                        {"T": "AMZN", "c": 192.53}],
        }

    def test_delivery_is_saved_once(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.dict(os.environ, {"MASSIVE_API_KEY": "test-key"}):
                with patch("pipeline.massive_prices.get_response",
                           return_value=self.response()) as request:
                    first = fetch("2024-09-25", root)
                    second = fetch("2024-09-25", root)
            self.assertEqual(first, second)
            request.assert_called_once_with("2024-09-25", "test-key")
            with first.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["universe_ticker"] for row in rows],
                             ["AAPL", "AMZN"])
            self.assertEqual(rows[0]["price_basis"], "unadjusted")
            staged = prepare(first, root, "2024-09-25")
            self.assertEqual(staged["rows"], 2)
            (first.parent / "response.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed"):
                fetch("2024-09-25", root)

    def test_adjusted_prices_are_rejected(self):
        response = self.response()
        response["adjusted"] = True
        with self.assertRaisesRegex(ValueError, "unadjusted"):
            price_rows("2024-09-25", response)

    def test_key_can_come_from_windows_vault(self):
        with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}):
            with patch("keyring.backends.Windows.WinVaultKeyring.get_password",
                       return_value="stored-test-key"):
                self.assertEqual(read_api_key(), "stored-test-key")

    def test_missing_or_repeated_bars_are_rejected(self):
        response = self.response()
        response["results"][1]["T"] = "AAPL"
        with self.assertRaisesRegex(ValueError, "duplicate ticker"):
            price_rows("2024-09-25", response)
        response["results"][1]["T"] = "AMZN"
        response["resultsCount"] = 3
        with self.assertRaisesRegex(ValueError, "result count"):
            price_rows("2024-09-25", response)


if __name__ == "__main__":
    unittest.main()
