import csv
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fund_pipeline.build_hybrid import build_hybrid
from data_extraction.fx_rates import download_fx
from fund_pipeline.gbp_reference import build_reference
from fund_pipeline.landing import land_delivery
from data_extraction.market_prices import DATES, download
from fund_pipeline.publication import approve, current, prepare, publish, show
from test_fx_reporting import synthetic_ecb


class GbpPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        def prices(value):
            return json.dumps([dict(date=day, open=value, high=value + 1, low=value - 1,
                                    close=value, volume=100) for day in DATES]).encode()
        with patch("data_extraction.market_prices.fetch", side_effect=[prices(100), prices(200)]):
            market = download(self.root / "market")
        scenario = build_hybrid(market, self.root)
        self.nav = Path(scenario["nav_delivery"])
        self.usd = Path(scenario["reference_delivery"])
        self.db = self.root / "gbp.sqlite"
        self.fx, self.reference = self.new_fx(synthetic_ecb())

    def new_fx(self, raw):
        with patch("data_extraction.fx_rates.fetch", return_value=raw):
            fx = download_fx(self.root / "synthetic_fx")
        # Test data is explicitly labelled, including the correction scenario.
        path = fx / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["source"] = "SYNTHETIC TEST ONLY, not an ECB revision"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return fx, build_reference(self.usd, fx, DATES[-1], self.root / "landing")

    def candidate(self, fx=None, reference=None):
        return prepare(self.db, self.nav, self.usd, DATES[0], DATES[-1], "GBP",
                       fx or self.fx, reference or self.reference)

    def test_publish_keeps_both_currencies_and_fx_evidence(self):
        candidate = self.candidate()
        with self.assertRaisesRegex(ValueError, "no recorded approval"):
            publish(self.db, candidate)
        approve(self.db, candidate, "demo-reviewer", "Synthetic check", 0)
        self.assertEqual(publish(self.db, candidate), 1)
        result = current(self.db, DATES[-1])
        self.assertEqual(Decimal(result["close"]["nav"]), 8000)
        self.assertEqual(Decimal(result["local_close"]["nav"]), 10000)
        self.assertEqual(result["fx_evidence"]["rate"]["valuation_date"], DATES[-1])

    def test_correction_requires_new_review_and_preserves_first_publication(self):
        first = self.candidate()
        approve(self.db, first, "demo-reviewer", "First synthetic rate", 0)
        publish(self.db, first)
        frozen = show(self.db, first)["candidate"]
        fx, reference = self.new_fx(synthetic_ecb().replace(b"1.00,GBP", b"0.90,GBP"))
        second = self.candidate(fx, reference)
        with self.assertRaisesRegex(ValueError, "no recorded approval"):
            publish(self.db, second)
        approve(self.db, second, "demo-reviewer", "Corrected synthetic rate", 1)
        self.assertEqual(publish(self.db, second), 2)
        self.assertEqual(Decimal(current(self.db, DATES[-1])["close"]["nav"]), 7200)
        self.assertEqual(show(self.db, first)["candidate"], frozen)
        self.assertEqual(publish(self.db, first), 1)
        self.assertEqual(current(self.db, DATES[-1])["publication"]["version"], 2)

    def test_old_reference_cannot_be_paired_with_new_fx(self):
        fx, _ = self.new_fx(synthetic_ecb().replace(b"1.00,GBP", b"0.90,GBP"))
        with self.assertRaisesRegex(ValueError, "different FX"):
            self.candidate(fx=fx)

    def test_wrong_gbp_nav_blocks_approval(self):
        source = self.root / "wrong"
        source.mkdir()
        path = self.reference / "gbp_reference.csv"
        (source / path.name).write_text(path.read_text().replace(",nav,8000", ",nav,9000"))
        manifest = json.loads((self.reference / "manifest.json").read_text())
        bad = land_delivery(source, self.root / "landing", DATES[-1], "gbp_references",
                            provenance=manifest["provenance"])
        candidate = self.candidate(reference=bad)
        self.assertEqual(show(self.db, candidate)["candidate"]["reconciliation"]["status"], "FAIL")
        with self.assertRaisesRegex(ValueError, "reconciliation did not pass"):
            approve(self.db, candidate, "demo-reviewer", "Must fail", 0)

    def test_usd_position_failure_blocks_even_when_gbp_nav_matches(self):
        source = self.root / "bad_usd"
        source.mkdir()
        for name in ("broker_positions.csv", "broker_cash.csv", "administrator_nav.csv"):
            (source / name).write_bytes((self.usd / name).read_bytes())
        path = source / "broker_positions.csv"
        path.write_text(path.read_text().replace("TRADE_DATE,10", "TRADE_DATE,9"))
        self.usd = land_delivery(source, self.root / "landing", DATES[-1], "references")
        reference = build_reference(self.usd, self.fx, DATES[-1], self.root / "landing")
        candidate = self.candidate(reference=reference)
        rows = show(self.db, candidate)["candidate"]["reconciliation"]["controls"]
        self.assertTrue(all(row["status"] == "PASS" for row in rows if row["control"] == "gbp_reference"))
        with self.assertRaisesRegex(ValueError, "reconciliation did not pass"):
            approve(self.db, candidate, "demo-reviewer", "Must fail USD", 0)

    def test_missing_fx_stops_preparation(self):
        with self.assertRaisesRegex(ValueError, "manifest missing"):
            self.candidate(fx=self.root / "missing")
        self.assertFalse(self.db.exists())

    def test_missing_reference_argument_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "both FX and GBP"):
            prepare(self.db, self.nav, self.usd, DATES[0], DATES[-1], fx_folder=self.fx)

    def test_source_changes_do_not_recalculate_reviewed_candidate(self):
        candidate = self.candidate()
        (self.fx / "usd_gbp.csv").write_text("broken input")
        approve(self.db, candidate, "demo-reviewer", "Review frozen evidence", 0)
        publish(self.db, candidate)
        self.assertEqual(Decimal(current(self.db, DATES[-1])["close"]["nav"]), 8000)


if __name__ == "__main__":
    unittest.main()
