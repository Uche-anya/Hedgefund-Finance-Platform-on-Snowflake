import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from build_positions import build_positions
from landing import land_delivery, verify_delivery


class PositionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "trades" / "2026-09-14"
        shutil.copytree(fixture, self.source)

    def calculate(self):
        return build_positions(self.source, "2026-09-14")

    def change(self, name, old, new):
        path = self.source / name
        path.write_text(path.read_text().replace(old, new))

    def test_saved_delivery_gives_hand_worked_positions(self):
        folder = land_delivery(self.source, self.root / "landing", "2026-09-14", "trades")
        verify_delivery(folder, "2026-09-14", "trades")
        result = build_positions(folder, "2026-09-14")
        self.assertEqual(result["positions"], [
            {"portfolio": "GROWTH", "instrument": "ALPHA", "quantity": Decimal("70")},
            {"portfolio": "HEDGE", "instrument": "BETA", "quantity": Decimal("-20")},
        ])
        self.assertEqual(result, build_positions(folder, "2026-09-14"))
        with self.assertRaisesRegex(ValueError, "Expected a valuation delivery"):
            verify_delivery(folder, "2026-09-14")

    def test_repeated_execution_and_allocation_have_no_extra_effect(self):
        for name in ("executions.csv", "allocations.csv"):
            path = self.source / name
            first_record = path.read_text().splitlines()[1]
            with path.open("a") as file:
                file.write(first_record + "\n")
        result = self.calculate()
        self.assertEqual(result["positions"][0]["quantity"], Decimal("70"))
        self.assertEqual(result["repeated_executions"], 1)
        self.assertEqual(result["repeated_allocations"], 1)

    def test_execution_can_be_split_between_portfolios(self):
        self.change("allocations.csv", "GROWTH,100", "GROWTH,60")
        with (self.source / "allocations.csv").open("a") as file:
            file.write("2026-09-14,A004,E001,HEDGE,40\n")
        positions = {(r["portfolio"], r["instrument"]): r["quantity"] for r in self.calculate()["positions"]}
        self.assertEqual(positions, {
            ("GROWTH", "ALPHA"): Decimal("30"),
            ("HEDGE", "ALPHA"): Decimal("40"),
            ("HEDGE", "BETA"): Decimal("-20"),
        })

    def test_missing_or_excess_allocation_stops_positions(self):
        path = self.source / "allocations.csv"
        original = path.read_text()
        for quantity in ("99", "101"):
            with self.subTest(quantity=quantity):
                path.write_text(original.replace("GROWTH,100", f"GROWTH,{quantity}"))
                with self.assertRaisesRegex(ValueError, "Allocation mismatch for E001"):
                    self.calculate()

    def test_conflicting_duplicate_is_not_treated_as_a_retry(self):
        for name, record in (
            ("executions.csv", "2026-09-14,E001,ALPHA,BUY,101\n"),
            ("allocations.csv", "2026-09-14,A001,E001,GROWTH,101\n"),
        ):
            with self.subTest(name=name):
                path = self.source / name
                original = path.read_text()
                path.write_text(original + record)
                with self.assertRaisesRegex(ValueError, "Conflicting"):
                    self.calculate()
                path.write_text(original)

    def test_unknown_execution_is_rejected(self):
        self.change("allocations.csv", "A001,E001", "A001,E999")
        with self.assertRaisesRegex(ValueError, "unknown execution E999"):
            self.calculate()

    def test_invalid_quantities_are_rejected(self):
        path = self.source / "executions.csv"
        original = path.read_text()
        for value in ("0", "-1", "NaN", "Infinity", "oops"):
            with self.subTest(value=value):
                path.write_text(original.replace("BUY,100", f"BUY,{value}"))
                with self.assertRaises(ValueError):
                    self.calculate()

    def test_wrong_date_and_unknown_side_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "expected business date"):
            build_positions(self.source, "2026-09-15")
        self.change("executions.csv", "BUY", "PURCHASE")
        with self.assertRaisesRegex(ValueError, "Unknown side"):
            self.calculate()
