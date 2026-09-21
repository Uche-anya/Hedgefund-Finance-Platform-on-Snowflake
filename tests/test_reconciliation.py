import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from landing import land_delivery, verify_delivery
from reconcile import reconcile, make_demo_delivery


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = Path(__file__).resolve().parents[1]
        self.nav_source = self.root / "nav_source"
        self.ref_source = self.root / "reference_source"
        shutil.copytree(self.repo / "fixtures" / "settlement" / "2026-09-14", self.nav_source)
        shutil.copytree(self.repo / "fixtures" / "references" / "2026-09-16", self.ref_source)

    def deliveries(self):
        nav = land_delivery(self.nav_source, self.root / "landing", "2026-09-14", "nav")
        refs = land_delivery(self.ref_source, self.root / "landing", "2026-09-16", "references")
        return nav, refs

    def calculate(self):
        nav, refs = self.deliveries()
        return reconcile(nav, refs, "2026-09-14", "2026-09-16")

    def test_independent_hand_worked_references_match(self):
        report = self.calculate()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["publication_status"], "NOT APPROVED")
        self.assertEqual(len(report["controls"]), 4)
        for row in report["controls"]:
            self.assertEqual(row["difference"], Decimal("0"))
            self.assertEqual(row["status"], "PASS")
        self.assertEqual(report["controls"][-1]["expected"], Decimal("10105"))

    def test_intentional_69_share_demo_fails_and_original_stays_unchanged(self):
        nav, refs = self.deliveries()
        before = (refs / "broker_positions.csv").read_bytes()
        demo = make_demo_delivery(refs, self.root / "landing", "2026-09-16")
        report = reconcile(nav, demo, "2026-09-14", "2026-09-16")
        failed = [row for row in report["controls"] if row["status"] == "FAIL"]
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["entity"], ["GROWTH", "ALPHA"])
        self.assertEqual(failed[0]["actual"], Decimal("70"))
        self.assertEqual(failed[0]["expected"], Decimal("69"))
        self.assertEqual(failed[0]["difference"], Decimal("1"))
        self.assertEqual((refs / "broker_positions.csv").read_bytes(), before)
        verify_delivery(refs, "2026-09-16", "references")
        self.assertEqual(reconcile(nav, refs, "2026-09-14", "2026-09-16")["status"], "PASS")

    def test_missing_reference_and_internal_records_both_fail(self):
        path = self.ref_source / "broker_positions.csv"
        lines = path.read_text().splitlines()
        lines = [line for line in lines if ",BETA," not in line]
        lines.append("2026-09-16,NORTHBRIDGE,GROWTH,GAMMA,TRADE_DATE,0")
        path.write_text("\n".join(lines) + "\n")
        failed = [row for row in self.calculate()["controls"] if row["status"] == "FAIL"]
        self.assertEqual({row["reason"] for row in failed}, {"MISSING_REFERENCE", "MISSING_INTERNAL"})
        for row in failed:
            self.assertIsNone(row["difference"])

    def test_duplicate_reference_keys_fail_for_each_feed(self):
        for name in ("broker_positions.csv", "broker_cash.csv", "administrator_nav.csv"):
            with self.subTest(name=name):
                path = self.ref_source / name
                original = path.read_text()
                path.write_text(original + original.splitlines()[1] + "\n")
                with self.assertRaisesRegex(ValueError, "duplicate reference key"):
                    self.calculate()
                path.write_text(original)

    def test_duplicate_internal_position_is_rejected(self):
        nav, refs = self.deliveries()
        duplicate = {"portfolio": "GROWTH", "instrument": "ALPHA", "quantity": Decimal("70")}
        with patch("reconcile.calculate_nav", return_value={"holdings": [duplicate, duplicate]}):
            with self.assertRaisesRegex(ValueError, "Duplicate internal position"):
                reconcile(nav, refs, "2026-09-14", "2026-09-16")

    def test_cash_and_nav_tolerance_boundary(self):
        for name, amount, control in (("broker_cash.csv", "9730", "broker_cash"),
                                      ("administrator_nav.csv", "10105", "administrator_nav")):
            path = self.ref_source / name
            original = path.read_text()
            for change, status in (("0.01", "PASS"), ("-0.01", "PASS"), ("0.02", "FAIL")):
                with self.subTest(name=name, change=change):
                    value = Decimal(amount) + Decimal(change)
                    path.write_text(original.replace(f"{amount}.00", str(value)))
                    row = next(r for r in self.calculate()["controls"] if r["control"] == control)
                    self.assertEqual(row["status"], status)
            path.write_text(original)

    def test_wrong_date_currency_basis_fund_and_invalid_values_fail(self):
        cases = (
            ("broker_cash.csv", "2026-09-16", "2026-09-15"),
            ("broker_cash.csv", "GBP", "USD"),
            ("broker_cash.csv", "SETTLED", "TRADE_DATE"),
            ("broker_positions.csv", "TRADE_DATE", "SETTLED"),
            ("administrator_nav.csv", "NORTHBRIDGE", "OTHER_FUND"),
            ("administrator_nav.csv", "10105.00", "NaN"),
            ("broker_cash.csv", "9730.00", "oops"),
        )
        for name, old, new in cases:
            with self.subTest(name=name, value=new):
                path = self.ref_source / name
                original = path.read_text()
                path.write_text(original.replace(old, new))
                with self.assertRaises(ValueError):
                    self.calculate()
                path.write_text(original)

    def test_empty_cash_statement_is_missing_not_zero(self):
        path = self.ref_source / "broker_cash.csv"
        path.write_text(path.read_text().splitlines()[0] + "\n")
        row = next(r for r in self.calculate()["controls"] if r["control"] == "broker_cash")
        self.assertEqual(row["status"], "FAIL")
        self.assertIsNone(row["expected"])

    def test_dropped_trade_is_detected_by_independent_references(self):
        for name in ("executions.csv", "allocations.csv", "execution_terms.csv", "settlements.csv"):
            path = self.nav_source / name
            lines = path.read_text().splitlines()
            path.write_text("\n".join(line for line in lines if ",E002," not in line) + "\n")
        report = self.calculate()
        self.assertEqual(report["status"], "FAIL")
        failed_controls = {r["control"] for r in report["controls"] if r["status"] == "FAIL"}
        self.assertEqual(failed_controls, {"broker_position", "broker_cash", "administrator_nav"})

    def test_cli_saves_report_and_returns_failure_for_demo(self):
        # Run a copied entry point so generated evidence stays in the temporary directory.
        shutil.copyfile(self.repo / "reconcile.py", self.root / "reconcile.py")
        for name in ("fund_nav.py", "cash_settlement.py", "build_positions.py", "daily_close.py", "landing.py"):
            shutil.copyfile(self.repo / name, self.root / name)
        nav, refs = self.deliveries()
        command = [sys.executable, str(self.root / "reconcile.py"), "--business-date", "2026-09-14",
                   "--as-of", "2026-09-16", "--delivery", str(nav), "--references", str(refs)]
        passed = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(passed.returncode, 0, passed.stderr)
        failed = subprocess.run(command + ["--demo-alpha-69"], capture_output=True, text=True, timeout=30)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertIn("difference=1 shares", failed.stdout)
        reports = [json.loads(path.read_text()) for path in (self.root / "data" / "reconciliation").glob("*.json")]
        self.assertEqual({r["status"] for r in reports}, {"PASS", "FAIL"})
        demo_report = next(r for r in reports if r["status"] == "FAIL")
        self.assertIn("INTENTIONAL TEST", demo_report["injected_fault"])
