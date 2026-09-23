import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from fund_pipeline.build_hybrid import build_hybrid
from fund_pipeline.fund_nav import calculate_nav
from data_extraction.market_prices import DATES, download, fetch, normalize, verify_market
from fund_pipeline.publication import prepare
from fund_pipeline.reconcile import reconcile
from fund_pipeline.landing import land_delivery


def synthetic_response(closes):
    # Invented prices with the provider's documented shape; no vendor data in tests.
    return json.dumps([{"date": day, "open": close, "high": close + 1, "low": close - 1,
                        "close": close, "adjusted_close": close - 10, "volume": 1000}
                       for day, close in zip(DATES, closes)]).encode()


class MarketPriceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.apple = synthetic_response([100, 101, 102])
        self.amazon = synthetic_response([200, 198, 197])

    def downloaded(self):
        with patch("data_extraction.market_prices.fetch", side_effect=[self.apple, self.amazon]):
            return download(self.root / "market")

    def test_raw_responses_are_preserved_and_close_not_adjusted_close_is_used(self):
        folder = self.downloaded()
        self.assertEqual((folder / "AAPL.US.json").read_bytes(), self.apple)
        rows = verify_market(folder)
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["close_price"], "100")
        self.assertEqual(rows[0]["currency"], "USD")
        manifest = json.loads((folder / "manifest.json").read_text())
        self.assertEqual(len(manifest["requests"]), 2)
        self.assertIn("api_token=demo", manifest["requests"][0]["url"])

    def test_missing_duplicate_invalid_dates_and_api_errors_fail(self):
        rows = json.loads(self.apple)
        cases = [[], {"error": "rate limit"}, rows[:-1], rows + [rows[0]],
                 [{**rows[0], "date": "2025-01-09"}] + rows[1:],
                 [{"date": DATES[0], "close": 100}]]
        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    normalize(json.dumps(payload).encode(), "AAPL.US")

    def test_bad_prices_volume_and_ranges_fail(self):
        for field, value in (("close", "NaN"), ("close", 0), ("close", -1),
                             ("high", 50), ("volume", -1), ("volume", 0.5)):
            with self.subTest(field=field, value=value):
                rows = json.loads(self.apple)
                rows[0][field] = value
                with self.assertRaises(ValueError):
                    normalize(json.dumps(rows).encode(), "AAPL.US")

    def test_changed_response_or_normalized_file_is_rejected(self):
        for name in ("AAPL.US.json", "closing_prices.csv"):
            folder = self.downloaded()
            with (folder / name).open("ab") as file:
                file.write(b"changed")
            with self.assertRaisesRegex(ValueError, "Changed market file"):
                verify_market(folder)

    def test_failed_second_response_keeps_raw_evidence_without_manifest(self):
        with patch("data_extraction.market_prices.fetch", side_effect=[self.apple, b'{"error":"unavailable"}']):
            with self.assertRaisesRegex(RuntimeError, "incomplete"):
                download(self.root / "market")
        folder = next((self.root / "market").iterdir())
        self.assertTrue((folder / "failure.json").exists())
        self.assertEqual((folder / "AMZN.US.json").read_bytes(), b'{"error":"unavailable"}')
        with self.assertRaisesRegex(ValueError, "manifest missing"):
            verify_market(folder)

    def test_transient_errors_retry_and_permanent_http_errors_do_not(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = self.apple
        with patch("data_extraction.market_prices.time.sleep"), patch("data_extraction.market_prices.urlopen", side_effect=[
            HTTPError("demo", 429, "rate limited", {}, None), URLError("timeout"), response
        ]) as request:
            self.assertEqual(fetch("https://example.invalid"), self.apple)
            self.assertEqual(request.call_count, 3)
        with patch("data_extraction.market_prices.time.sleep"), patch("data_extraction.market_prices.urlopen", side_effect=URLError("down")) as request:
            with self.assertRaises(URLError):
                fetch("https://example.invalid")
            self.assertEqual(request.call_count, 3)
        with patch("data_extraction.market_prices.urlopen", side_effect=HTTPError("demo", 401, "denied", {}, None)) as request:
            with self.assertRaises(HTTPError):
                fetch("https://example.invalid")
            self.assertEqual(request.call_count, 1)

    def test_hybrid_runs_existing_controls_in_usd_without_relabelling(self):
        scenario = build_hybrid(self.downloaded(), self.root)
        nav, refs = Path(scenario["nav_delivery"]), Path(scenario["reference_delivery"])
        result = reconcile(nav, refs, DATES[0], DATES[-1], currency="USD")
        self.assertEqual(result["status"], "PASS")
        # Independent hand answer: Apple gains 20; Amazon short gains 15.
        self.assertEqual(str(result["close"]["nav"]), "10035.00")
        self.assertEqual(result["close"]["currency"], "USD")
        with self.assertRaises(ValueError):
            calculate_nav(nav, DATES[0], DATES[-1])  # GBP default must reject USD inputs.
        manifest = json.loads((nav / "manifest.json").read_text())
        self.assertEqual(manifest["source"], "hybrid_eodhd_and_simulated_activity")
        self.assertFalse(manifest["provenance"]["fx_conversion"])

    def test_missing_usd_price_still_blocks_nav(self):
        scenario = build_hybrid(self.downloaded(), self.root)
        nav = Path(scenario["nav_delivery"])
        path = nav / "closing_prices.csv"
        path.write_text("\n".join(line for line in path.read_text().splitlines()
                                   if not line.startswith("2025-01-08,AMZN.US,")) + "\n")
        with self.assertRaisesRegex(ValueError, "Missing closing price"):
            calculate_nav(nav, DATES[0], DATES[-1], "USD")

    def test_publication_database_cannot_mix_gbp_and_usd_scenarios(self):
        scenario = build_hybrid(self.downloaded(), self.root)
        db = self.root / "hybrid.sqlite"
        prepare(db, Path(scenario["nav_delivery"]), Path(scenario["reference_delivery"]), DATES[0], DATES[-1], "USD")
        repo = Path(__file__).resolve().parents[1]
        nav = land_delivery(repo / "fixtures" / "settlement" / "2026-09-14", self.root / "landing", "2026-09-14", "nav")
        refs = land_delivery(repo / "fixtures" / "references" / "2026-09-16", self.root / "landing", "2026-09-16", "references")
        with self.assertRaisesRegex(ValueError, "separate publication database"):
            prepare(db, nav, refs, "2026-09-14", "2026-09-16")
