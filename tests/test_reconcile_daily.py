from decimal import Decimal
from pathlib import Path
import shutil
import unittest

from fund_pipeline.landing import land_delivery
from fund_pipeline.publication import check_eligible
from fund_pipeline.reconcile_daily import make_mismatch, reconcile_daily
import test_daily_nav


class DailyReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_daily_nav.DailyNavTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.f.root
        self.db = self.fixture.f.db
        self.activity = land_delivery(self.fixture.source, self.root / "landing", "2025-01-09", "daily_cash")
        self.prices = land_delivery(self.fixture.prices, self.root / "landing", "2025-01-09", "daily_prices")
        self.references = self.root / "references"
        source = Path(__file__).resolve().parents[1] / "fixtures" / "daily_references" / "2025-01-09"
        shutil.copytree(source, self.references)
        # Independent constants for this test's synthetic USD 10,000 opening:
        # cash = 10,000 - 440; NAV = cash + 13*245 - 3*225 - 720.
        for name, before, after in (("broker_cash.csv", "8248.05", "9560.00"),
                                    ("administrator_nav.csv", "10038.05", "11350.00")):
            path = self.references / name
            path.write_text(path.read_text().replace(before, after))

    def land_references(self):
        return land_delivery(self.references, self.root / "landing", "2025-01-09", "daily_references")

    def calculate(self, references=None):
        return reconcile_daily(self.db, "2025-01-08", self.activity, self.prices,
                               references or self.land_references(), "2025-01-09")

    def test_separately_prepared_statements_pass(self):
        report = self.calculate()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(len(report["controls"]), 7)
        self.assertEqual(report["review_eligibility"], "ELIGIBLE_FOR_REVIEW")
        self.assertEqual(report["publication_status"], "NOT APPROVED")
        check_eligible({"reconciliation": report})

    def test_apple_12_blocks_gate_without_changing_original_delivery(self):
        references = self.land_references()
        original = (references / "broker_positions.csv").read_bytes()
        wrong = make_mismatch(references, self.root / "landing", "2025-01-09")
        report = self.calculate(wrong)
        failure = next(row for row in report["controls"] if row["status"] == "FAIL")
        self.assertEqual(failure["difference"], Decimal(1))
        self.assertEqual(report["review_eligibility"], "BLOCKED")
        with self.assertRaisesRegex(ValueError, "reconciliation did not pass"):
            check_eligible({"reconciliation": report})
        self.assertEqual((references / "broker_positions.csv").read_bytes(), original)

    def test_cash_nav_and_missing_obligation_each_block(self):
        for name in ("broker_cash.csv", "administrator_nav.csv", "open_obligations.csv"):
            path = self.references / name
            original = path.read_text()
            with self.subTest(file=name):
                if name == "open_obligations.csv":
                    path.write_text(original.splitlines()[0] + "\n")
                else:
                    path.write_text(original.replace("9560.00", "9562.00").replace("11350.00", "11352.00"))
                report = self.calculate()
                self.assertEqual(report["status"], "FAIL")
                self.assertEqual(report["review_eligibility"], "BLOCKED")
            path.write_text(original)

    def test_wrong_obligation_identity_blocks_even_when_totals_match(self):
        path = self.references / "open_obligations.csv"
        path.write_text(path.read_text().replace("SIM-D2-E001", "WRONG-TRADE"))
        report = self.calculate()
        self.assertEqual(report["review_eligibility"], "BLOCKED")
        self.assertTrue(all(row["status"] == "PASS" for row in report["controls"] if row["control"] == "obligation_total"))

    def test_bad_reference_date_currency_and_duplicate_keys_are_rejected(self):
        path = self.references / "broker_cash.csv"
        original = path.read_text()
        for text in (original.replace("2025-01-09", "2025-01-08"), original.replace("USD", "GBP"),
                     original + original.splitlines()[1] + "\n"):
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    self.calculate()


if __name__ == "__main__":
    unittest.main()
