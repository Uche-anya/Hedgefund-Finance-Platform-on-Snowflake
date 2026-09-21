import copy
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from build_hybrid import build_hybrid
from daily_close import pounds
from fx_rates import download_fx, normalize, verify_fx
from market_prices import DATES, download
from report_gbp import calculate_gbp, translate


def synthetic_ecb():
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["TIME_PERIOD", "OBS_VALUE", "CURRENCY", "CURRENCY_DENOM", "FREQ", "EXR_TYPE", "EXR_SUFFIX", "UNIT_MULT"])
    for day, gbp in zip(DATES, ("1.00", "0.90", "1.00")):
        writer.writerow([day, "1.25", "USD", "EUR", "D", "SP00", "A", "0"])
        writer.writerow([day, gbp, "GBP", "EUR", "D", "SP00", "A", "0"])
    return output.getvalue().encode()


class FxReportingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw = synthetic_ecb()

    def fx_delivery(self):
        with patch("fx_rates.fetch", return_value=self.raw):
            return download_fx(self.root / "fx")

    def nav_delivery(self):
        def payload(price):
            return json.dumps([{"date": day, "open": price, "high": price + 1, "low": price - 1,
                                "close": price, "volume": 100} for day in DATES]).encode()
        with patch("market_prices.fetch", side_effect=[payload(100), payload(200)]):
            market = download(self.root / "market")
        return Path(build_hybrid(market, self.root)["nav_delivery"])

    def test_known_cross_rate_direction_and_preserved_source(self):
        folder = self.fx_delivery()
        self.assertEqual((folder / "ecb_rates.csv").read_bytes(), self.raw)
        rates = verify_fx(folder)
        self.assertEqual(Decimal(rates[DATES[0]]["gbp_per_usd"]), Decimal("0.8"))
        self.assertEqual(Decimal(rates[DATES[1]]["gbp_per_usd"]), Decimal("0.72"))
        self.assertEqual(rates[DATES[0]]["from_currency"], "USD")

    def test_converts_all_components_before_and_after_settlement(self):
        nav, fx = self.nav_delivery(), self.fx_delivery()
        before = calculate_gbp(nav, fx, DATES[0], DATES[0])
        gbp = before["reporting_close"]
        self.assertEqual(gbp["cash"], Decimal("8000"))
        self.assertEqual(gbp["receivables"], Decimal("800"))
        self.assertEqual(gbp["payables"], Decimal("800"))
        self.assertEqual(gbp["long_assets"], Decimal("800"))
        self.assertEqual(gbp["short_obligations"], Decimal("800"))
        self.assertEqual(gbp["nav"], Decimal("8000"))
        self.assertEqual({row["amount"] for row in gbp["obligations"]}, {Decimal("800")})
        self.assertEqual([row["quantity"] for row in gbp["holdings"]], [Decimal("10"), Decimal("-5")])
        after = calculate_gbp(nav, fx, DATES[0], DATES[-1])
        self.assertEqual(after["reporting_close"]["nav"], Decimal("8000"))
        self.assertEqual(after["reporting_close"]["receivables"], 0)
        self.assertEqual(after["local_close"]["nav"], Decimal("10000"))

    def test_only_fx_moves_gbp_nav_when_usd_nav_is_constant(self):
        nav, fx = self.nav_delivery(), self.fx_delivery()
        first = calculate_gbp(nav, fx, DATES[0], DATES[0])
        second = calculate_gbp(nav, fx, DATES[0], DATES[1])
        self.assertEqual(first["local_close"]["nav"], second["local_close"]["nav"])
        self.assertEqual(second["reporting_close"]["nav"], Decimal("7200"))

    def test_missing_requested_date_stops_before_valuation(self):
        with self.assertRaisesRegex(ValueError, "Missing FX rate"):
            calculate_gbp(self.nav_delivery(), self.fx_delivery(), DATES[0], "2025-01-09")

    def test_missing_leg_or_duplicate_observation_rejected(self):
        lines = self.raw.decode().splitlines()
        for payload in ("\n".join(lines[:-1]), "\n".join(lines + [lines[1]])):
            with self.assertRaises(ValueError):
                normalize(payload.encode())

    def test_bad_units_dates_currencies_and_values_rejected(self):
        for old, new in (("1.25", "NaN"), ("1.25", "0"), ("1.25", "-1"),
                         ("1.25", "bad"), (",EUR,", ",USD,"), (",D,", ",M,"),
                         (",SP00,", ",OTHER,"), (",A,0", ",A,3"),
                         ("2025-01-06", "2025-01-09"), ("OBS_VALUE", "unknown_field")):
            with self.subTest(value=new):
                with self.assertRaises(ValueError):
                    normalize(self.raw.replace(old.encode(), new.encode()))

    def test_failed_download_preserves_raw_and_has_no_ready_manifest(self):
        with patch("fx_rates.fetch", return_value=b"service unavailable"):
            with self.assertRaisesRegex(RuntimeError, "Incomplete FX"):
                download_fx(self.root / "fx")
        folder = next((self.root / "fx").iterdir())
        self.assertEqual((folder / "ecb_rates.csv").read_bytes(), b"service unavailable")
        self.assertTrue((folder / "failure.json").exists())
        with self.assertRaisesRegex(ValueError, "manifest missing"):
            verify_fx(folder)

    def test_modified_rate_or_reversed_direction_is_rejected(self):
        folder = self.fx_delivery()
        path = folder / "usd_gbp.csv"
        path.write_bytes(path.read_bytes().replace(b"0.800000000000", b"1.250000000000"))
        with self.assertRaisesRegex(ValueError, "Changed FX file"):
            verify_fx(folder)
        manifest_path = folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["sha256"]["usd_gbp.csv"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        # Even with a matching new checksum, the rate must agree with its raw legs.
        with self.assertRaisesRegex(ValueError, "do not match original"):
            verify_fx(folder)
        manifest["from_currency"], manifest["to_currency"] = "GBP", "USD"
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "direction"):
            verify_fx(folder)

    def test_translation_preserves_usd_and_rounds_only_for_display(self):
        usd = {"currency": "USD", "cash": Decimal("1.01"), "receivables": Decimal("1.01"),
               "payables": Decimal("0"), "long_assets": Decimal("1.01"),
               "short_obligations": Decimal("0"), "nav": Decimal("3.03"),
               "holdings": [{"quantity": Decimal("1"), "market_value": Decimal("1.01")}],
               "obligations": [{"amount": Decimal("1.01"), "type": "RECEIVABLE"}]}
        original = copy.deepcopy(usd)
        fx = {"from_currency": "USD", "to_currency": "GBP", "gbp_per_usd": "0.8"}
        gbp = translate(usd, fx)
        self.assertEqual(usd, original)
        self.assertEqual(gbp["nav"], Decimal("2.424"))
        self.assertEqual(pounds(gbp["nav"]), "2.42")
        with self.assertRaisesRegex(ValueError, "Expected USD"):
            translate({**usd, "currency": "GBP"}, fx)

    def test_inconsistent_local_nav_is_rejected(self):
        report = calculate_gbp(self.nav_delivery(), self.fx_delivery(), DATES[0], DATES[-1])
        report["local_close"]["nav"] += Decimal("1")
        with self.assertRaisesRegex(ValueError, "do not agree"):
            translate(report["local_close"], report["fx"])
