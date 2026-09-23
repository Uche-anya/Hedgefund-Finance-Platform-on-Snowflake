import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from fund_pipeline.fund_nav import calculate_nav
from fund_pipeline.landing import land_delivery, verify_delivery


class FundNavTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "settlement" / "2026-09-14"
        shutil.copytree(fixture, self.source)

    def calculate(self, as_of="2026-09-16"):
        return calculate_nav(self.source, "2026-09-14", as_of)

    def test_hand_worked_nav_is_unchanged_by_settlement(self):
        for day, cash, receivables, payables in (
            ("2026-09-14", "10000", "730", "1000"),
            ("2026-09-15", "9000", "730", "0"),
            ("2026-09-16", "9730", "0", "0"),
        ):
            with self.subTest(day=day):
                result = self.calculate(day)
                self.assertEqual(result["nav"], Decimal("10105"))
                self.assertEqual(result["long_assets"], Decimal("735"))
                self.assertEqual(result["short_obligations"], Decimal("360"))
                self.assertEqual(result["cash"], Decimal(cash))
                self.assertEqual(result["receivables"], Decimal(receivables))
                self.assertEqual(result["payables"], Decimal(payables))

    def test_missing_short_price_blocks_nav_despite_prior_day_price(self):
        path = self.source / "closing_prices.csv"
        path.write_text(path.read_text().replace("2026-09-16,BETA,GBP,18.00\n", ""))
        with self.assertRaisesRegex(ValueError, "Missing closing price for BETA on 2026-09-16"):
            self.calculate()

    def test_missing_valuation_date_cannot_use_previous_prices(self):
        with self.assertRaisesRegex(ValueError, "Missing closing price"):
            self.calculate("2026-09-17")

    def test_duplicate_price_blocks_nav(self):
        with (self.source / "closing_prices.csv").open("a") as file:
            file.write("2026-09-16,ALPHA,GBP,10.50\n")
        with self.assertRaisesRegex(ValueError, "Duplicate closing price"):
            self.calculate()

    def test_invalid_prices_currency_and_schema_are_rejected(self):
        path = self.source / "closing_prices.csv"
        original = path.read_text()
        for old, new in (("18.00", "NaN"), ("18.00", "Infinity"), ("18.00", "0"),
                         ("18.00", "-1"), ("18.00", "oops"), ("GBP", "USD"),
                         ("valuation_date", "wrong_column")):
            with self.subTest(new=new):
                path.write_text(original.replace(old, new))
                with self.assertRaises(ValueError):
                    self.calculate()

    def test_price_change_creates_new_nav_and_preserves_saved_original(self):
        original = land_delivery(self.source, self.root / "landing", "2026-09-14", "nav")
        path = self.source / "closing_prices.csv"
        path.write_text(path.read_text().replace("2026-09-16,BETA,GBP,18.00",
                                                "2026-09-16,BETA,GBP,19.00"))
        changed = land_delivery(self.source, self.root / "landing", "2026-09-14", "nav")
        for folder, expected in ((original, "10105"), (changed, "10085")):
            verify_delivery(folder, "2026-09-14", "nav")
            self.assertEqual(calculate_nav(folder, "2026-09-14", "2026-09-16")["nav"],
                             Decimal(expected))

    def test_unsettled_purchase_keeps_liability_in_nav(self):
        path = self.source / "settlements.csv"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(line for line in lines if ",S001," not in line) + "\n")
        result = self.calculate()
        self.assertEqual(result["cash"], Decimal("10730"))
        self.assertEqual(result["payables"], Decimal("1000"))
        self.assertEqual(result["nav"], Decimal("10105"))
        self.assertEqual(result["obligations"][0]["status"], "OVERDUE")

    def test_trade_and_settlement_repeats_do_not_inflate_nav(self):
        for name in ("executions.csv", "allocations.csv", "settlements.csv"):
            path = self.source / name
            line = path.read_text().splitlines()[1]
            with path.open("a") as file:
                file.write(line + "\n")
        self.assertEqual(self.calculate()["nav"], Decimal("10105"))

    def test_upstream_allocation_break_blocks_nav(self):
        path = self.source / "allocations.csv"
        path.write_text(path.read_text().replace("GROWTH,100", "GROWTH,99"))
        with self.assertRaisesRegex(ValueError, "Allocation mismatch"):
            self.calculate()
