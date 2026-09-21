import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from cash_settlement import calculate_cash
from landing import land_delivery, verify_delivery


class CashSettlementTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "settlement" / "2026-09-14"
        shutil.copytree(fixture, self.source)

    def calculate(self, as_of="2026-09-16"):
        return calculate_cash(self.source, "2026-09-14", as_of)

    def change(self, name, old, new):
        path = self.source / name
        path.write_text(path.read_text().replace(old, new))

    def test_hand_worked_balances_before_during_and_after_settlement(self):
        # Fixed independent answers: buy 1,000; sell 330; short-sale proceeds 400.
        for day, cash, receivables, payables in (
            ("2026-09-14", "10000", "730", "1000"),
            ("2026-09-15", "9000", "730", "0"),
            ("2026-09-16", "9730", "0", "0"),
        ):
            with self.subTest(day=day):
                result = self.calculate(day)
                self.assertEqual(result["cash"], Decimal(cash))
                self.assertEqual(result["receivables"], Decimal(receivables))
                self.assertEqual(result["payables"], Decimal(payables))
                self.assertEqual(result["net_cash_and_obligations"], Decimal("9730"))
                self.assertEqual([r["quantity"] for r in result["positions"]],
                                 [Decimal("70"), Decimal("-20")])

    def test_due_date_without_confirmation_does_not_move_cash(self):
        path = self.source / "settlements.csv"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(line for line in lines if ",S001," not in line) + "\n")
        result = self.calculate()
        self.assertEqual(result["cash"], Decimal("10730"))
        self.assertEqual(result["payables"], Decimal("1000"))
        self.assertEqual(result["net_cash_and_obligations"], Decimal("9730"))
        self.assertEqual(result["obligations"][0]["status"], "OVERDUE")

    def test_late_confirmation_only_moves_cash_on_actual_date(self):
        self.change("settlements.csv", "1000.00,2026-09-15", "1000.00,2026-09-17")
        self.assertEqual(self.calculate()["cash"], Decimal("10730"))
        self.assertEqual(self.calculate()["obligations"][0]["status"], "OVERDUE")
        result = self.calculate("2026-09-17")
        self.assertEqual(result["cash"], Decimal("9730"))
        self.assertEqual(result["payables"], Decimal("0"))

    def test_duplicate_trades_allocations_and_confirmations_do_not_double_cash(self):
        for name in ("executions.csv", "allocations.csv", "settlements.csv"):
            path = self.source / name
            first_record = path.read_text().splitlines()[1]
            with path.open("a") as file:
                file.write(first_record + "\n")
        result = self.calculate()
        self.assertEqual(result["cash"], Decimal("9730"))
        self.assertEqual(result["repeated_settlements"], 1)

    def test_split_allocations_do_not_multiply_fund_cash(self):
        self.change("allocations.csv", "GROWTH,100", "GROWTH,60")
        with (self.source / "allocations.csv").open("a") as file:
            file.write("2026-09-14,A004,E001,HEDGE,40\n")
        self.assertEqual(self.calculate()["cash"], Decimal("9730"))

    def test_partial_or_wrong_amount_is_rejected(self):
        self.change("settlements.csv", "1000.00", "500.00")
        with self.assertRaisesRegex(ValueError, "Settlement amount mismatch"):
            self.calculate()

    def test_second_confirmation_for_same_trade_is_rejected(self):
        with (self.source / "settlements.csv").open("a") as file:
            file.write("2026-09-14,S004,E001,GBP,1000.00,2026-09-15\n")
        with self.assertRaisesRegex(ValueError, "Multiple settlement confirmations"):
            self.calculate()

    def test_conflicting_confirmation_id_is_rejected(self):
        with (self.source / "settlements.csv").open("a") as file:
            file.write("2026-09-14,S001,E001,GBP,999.00,2026-09-15\n")
        with self.assertRaisesRegex(ValueError, "Conflicting settlement_id"):
            self.calculate()

    def test_unknown_execution_and_missing_terms_are_rejected(self):
        path = self.source / "settlements.csv"
        original = path.read_text()
        path.write_text(original.replace("S001,E001", "S001,E999"))
        with self.assertRaisesRegex(ValueError, "unknown execution"):
            self.calculate()
        path.write_text(original)
        self.change("execution_terms.csv", "E001", "E999")
        with self.assertRaisesRegex(ValueError, "terms must match"):
            self.calculate()

    def test_currency_dates_and_invalid_price_are_rejected(self):
        changes = (
            ("execution_terms.csv", "GBP", "USD"),
            ("settlements.csv", "GBP", "USD"),
            ("opening_cash.csv", "GBP", "USD"),
            ("execution_terms.csv", "10.00", "NaN"),
            ("execution_terms.csv", "10.00", "0"),
            ("execution_terms.csv", "2026-09-15", "2026-09-13"),
            ("settlements.csv", "2026-09-15", "2026-09-13"),
            ("settlements.csv", "2026-09-15", "not-a-date"),
            ("execution_terms.csv", "10.00", "10.00001"),
        )
        for name, old, new in changes:
            with self.subTest(name=name, value=new):
                path = self.source / name
                original = path.read_text()
                path.write_text(original.replace(old, new))
                with self.assertRaises(ValueError):
                    self.calculate()
                path.write_text(original)
        with self.assertRaisesRegex(ValueError, "As-of date"):
            self.calculate("2026-09-13")

    def test_allocation_break_blocks_cash_calculation(self):
        self.change("allocations.csv", "GROWTH,100", "GROWTH,99")
        with self.assertRaisesRegex(ValueError, "Allocation mismatch"):
            self.calculate()

    def test_saved_delivery_replay_uses_original_opening_cash(self):
        folder = land_delivery(self.source, self.root / "landing", "2026-09-14", "settlement")
        verify_delivery(folder, "2026-09-14", "settlement")
        for _ in range(2):
            self.assertEqual(calculate_cash(folder, "2026-09-14", "2026-09-16")["cash"],
                             Decimal("9730"))
        self.change("opening_cash.csv", "10000.00", "50000.00")
        self.assertEqual(calculate_cash(folder, "2026-09-14", "2026-09-16")["cash"],
                         Decimal("9730"))
