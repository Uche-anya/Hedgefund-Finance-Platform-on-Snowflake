from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from historical_prices import download, inspect_bars, read_symbols


def response(symbol):
    # Fictional bar in the provider's shape, not downloaded market data.
    timestamp = int(datetime.fromisoformat("2025-01-06T00:00:00-05:00").timestamp() * 1000)
    return {"status": "OK", "ticker": symbol, "adjusted": False, "resultsCount": 1,
            "results": [{"t": timestamp, "o": 100, "h": 102, "l": 99, "c": 101, "v": 500}]}


class HistoricalPricesTests(unittest.TestCase):
    def test_saves_original_responses_and_manifest_without_key(self):
        payloads = [json.dumps(response(symbol)).encode() for symbol in ("AAPL", "AMZN")]
        with tempfile.TemporaryDirectory() as temp:
            with patch("historical_prices.fetch", side_effect=payloads), patch("historical_prices.time.sleep"):
                folder = download(Path(temp), "test-secret", symbols=["AAPL", "AMZN"])
            self.assertEqual((folder / "AAPL.json").read_bytes(), payloads[0])
            manifest_text = (folder / "manifest.json").read_text()
            self.assertNotIn("test-secret", manifest_text)
            self.assertEqual(json.loads(manifest_text)["row_count"], 2)

    def test_errors_adjustments_pagination_duplicates_and_bad_prices_fail(self):
        cases = []
        for changes in ({"status": "ERROR"}, {"adjusted": True}, {"ticker": "OTHER"},
                        {"next_url": "https://api.massive.com/next"}, {"resultsCount": 9}):
            cases.append({**response("AAPL"), **changes})
        duplicate = response("AAPL")
        duplicate["results"] *= 2
        duplicate["resultsCount"] = 2
        cases.append(duplicate)
        for value in (0, 200, "wrong", float("nan")):
            data = response("AAPL")
            data["results"][0]["c"] = value
            cases.append(data)
        for data in cases:
            with self.subTest(data=data), self.assertRaises(ValueError):
                inspect_bars(json.dumps(data).encode(), "AAPL")

    def test_partial_download_has_no_completion_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("historical_prices.fetch", side_effect=[json.dumps(response("AAPL")).encode(),
                                                               RuntimeError("network failed")]), \
                    patch("historical_prices.time.sleep"):
                with self.assertRaises(RuntimeError):
                    download(Path(temp), "test-secret", symbols=["AAPL", "AMZN"])
            self.assertEqual(len(list(Path(temp).glob("*/AAPL.json"))), 1)
            self.assertEqual(list(Path(temp).glob("*/manifest.json")), [])

    def test_resume_fetches_only_unfinished_tickers_and_keeps_original_dates(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("historical_prices.fetch", side_effect=[json.dumps(response("AAPL")).encode(),
                                                               RuntimeError("network failed")]), \
                    patch("historical_prices.time.sleep"):
                with self.assertRaises(RuntimeError):
                    download(Path(temp), "test-secret", symbols=["AAPL", "AMZN"])
            folder = next(Path(temp).iterdir())
            plan = json.loads((folder / "request.json").read_text())
            apple_bytes = (folder / "AAPL.json").read_bytes()
            with patch("historical_prices.fetch", return_value=json.dumps(response("AMZN")).encode()) as fetch:
                download(Path(temp), "test-secret", resume=folder)
            fetch.assert_called_once_with("AMZN", "test-secret", plan["start"], plan["end"])
            self.assertEqual((folder / "AAPL.json").read_bytes(), apple_bytes)
            self.assertEqual(json.loads((folder / "manifest.json").read_text())["row_count"], 2)
            (folder / "AAPL.json").write_text("changed")
            with patch("historical_prices.fetch") as fetch:
                with self.assertRaisesRegex(ValueError, "Saved file changed"):
                    download(Path(temp), "test-secret", resume=folder)
                fetch.assert_not_called()

    def test_saved_universe_is_broad_unique_and_includes_simulator_stocks(self):
        symbols = read_symbols()
        self.assertGreaterEqual(len(symbols), 490)
        self.assertEqual(len(symbols), len(set(symbols)))
        self.assertTrue({"AAPL", "AMZN"}.issubset(symbols))


if __name__ == "__main__":
    unittest.main()
