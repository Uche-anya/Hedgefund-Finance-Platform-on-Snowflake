from decimal import Decimal
from pathlib import Path
import unittest

from carry_positions import carry_positions
from landing import land_delivery
from publication import approve, publish
import test_gbp_publication


class CarryPositionsTests(unittest.TestCase):
    def setUp(self):
        self.f = test_gbp_publication.GbpPublicationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.candidate = self.f.candidate()
        approve(self.f.db, self.candidate, "demo-reviewer", "Synthetic opening close", 0)
        publish(self.f.db, self.candidate)

    def trades(self, executions, allocations):
        folder = self.f.root / "day_two"
        folder.mkdir(exist_ok=True)
        (folder / "executions.csv").write_text(
            "business_date,execution_id,instrument,side,quantity\n" + executions)
        (folder / "allocations.csv").write_text(
            "business_date,allocation_id,execution_id,portfolio,quantity\n" + allocations)
        return land_delivery(folder, self.f.root / "landing", "2025-01-09", "trades")

    def calculate(self, folder):
        return carry_positions(self.f.db, "2025-01-08", folder, "2025-01-09")

    def test_next_day_buy_and_short_cover_are_replayable(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "trades" / "2025-01-09"
        folder = land_delivery(fixture, self.f.root / "landing", "2025-01-09", "trades")
        first, second = self.calculate(folder), self.calculate(folder)
        self.assertEqual(first["positions"], second["positions"])
        self.assertEqual([row["closing_quantity"] for row in first["positions"]], [Decimal(13), Decimal(-3)])
        self.assertEqual(first["opening_publication"]["candidate_id"], self.candidate)
        self.assertEqual(first["opening_publication"]["version"], 1)

    def test_no_trades_carries_all_holdings_unchanged(self):
        report = self.calculate(self.trades("", ""))
        self.assertEqual([row["closing_quantity"] for row in report["positions"]], [Decimal(10), Decimal(-5)])
        self.assertTrue(all(row["trade_change"] == 0 for row in report["positions"]))

    def test_sale_crosses_zero_and_new_position_is_added(self):
        folder = self.trades("2025-01-09,E1,AAPL.US,SELL,12\n2025-01-09,E2,TEST,BUY,4\n",
                             "2025-01-09,A1,E1,GROWTH,12\n2025-01-09,A2,E2,GROWTH,4\n")
        rows = {row["instrument"]: row for row in self.calculate(folder)["positions"]}
        self.assertEqual(rows["AAPL.US"]["closing_quantity"], -2)
        self.assertEqual(rows["TEST"]["opening_quantity"], 0)
        self.assertEqual(rows["TEST"]["closing_quantity"], 4)
        self.assertEqual(rows["AMZN.US"]["closing_quantity"], -5)

    def test_exact_duplicate_trade_does_not_double_movement(self):
        execution = "2025-01-09,E1,AAPL.US,BUY,3\n"
        allocation = "2025-01-09,A1,E1,GROWTH,3\n"
        report = self.calculate(self.trades(execution * 2, allocation * 2))
        self.assertEqual(report["positions"][0]["closing_quantity"], 13)
        self.assertEqual(report["repeated_executions"], 1)
        self.assertEqual(report["repeated_allocations"], 1)

    def test_mismatched_allocations_stop_carry_forward(self):
        folder = self.trades("2025-01-09,E1,AAPL.US,BUY,3\n", "2025-01-09,A1,E1,GROWTH,2\n")
        with self.assertRaisesRegex(ValueError, "Allocation mismatch"):
            self.calculate(folder)

    def test_unpublished_opening_and_skipped_date_are_rejected(self):
        folder = self.trades("", "")
        self.f.db = self.f.root / "unpublished.sqlite"
        self.f.candidate()
        with self.assertRaisesRegex(ValueError, "No published close"):
            self.calculate(folder)
        with self.assertRaisesRegex(ValueError, "next weekday close"):
            carry_positions(self.f.db, "2025-01-08", folder, "2025-01-10")


if __name__ == "__main__":
    unittest.main()
