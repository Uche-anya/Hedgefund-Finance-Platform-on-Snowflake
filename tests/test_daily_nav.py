from decimal import Decimal
from pathlib import Path
import shutil
import unittest

from daily_nav import daily_nav
from landing import land_delivery
from publication import approve, publish
import test_gbp_publication


class DailyNavTests(unittest.TestCase):
    def setUp(self):
        self.f = test_gbp_publication.GbpPublicationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        candidate = self.f.candidate()
        approve(self.f.db, candidate, "demo-reviewer", "Synthetic opening", 0)
        publish(self.f.db, candidate)
        fixtures = Path(__file__).resolve().parents[1] / "fixtures"
        self.source = self.f.root / "activity"
        shutil.copytree(fixtures / "daily_cash" / "2025-01-09", self.source)
        self.prices = self.f.root / "prices"
        shutil.copytree(fixtures / "daily_prices" / "2025-01-09", self.prices)

    def calculate(self):
        activity = land_delivery(self.source, self.f.root / "landing", "2025-01-09", "daily_cash")
        prices = land_delivery(self.prices, self.f.root / "landing", "2025-01-09", "daily_prices")
        return daily_nav(self.f.db, "2025-01-08", activity, prices, "2025-01-09")

    def test_hand_calculation_and_replay(self):
        first, second = self.calculate(), self.calculate()
        close = first["close"]
        # Synthetic opening cash is 10,000: 10,000 - 440 + 13*245 - 3*225 - 720.
        self.assertEqual(close["nav"], Decimal("11350.00"))
        self.assertEqual(close["long_assets"], 3185)
        self.assertEqual(close["short_obligations"], 675)
        self.assertEqual([row["quantity"] for row in close["holdings"]], [13, -3])
        self.assertEqual(close, second["close"])
        self.assertEqual(first["opening_publication"], second["opening_publication"])

    def test_settlement_moves_cash_and_removes_payable_without_changing_nav(self):
        before = self.calculate()["close"]
        with (self.source / "settlements.csv").open("a") as file:
            file.write("2025-01-09,APPLE-SETTLED,SIM-D2-E001,USD,720.00,2025-01-09\n")
        after = self.calculate()["close"]
        self.assertEqual(after["cash"], before["cash"] - 720)
        self.assertEqual(after["payables"], 0)
        self.assertEqual(after["nav"], before["nav"])

    def test_higher_short_price_reduces_nav(self):
        before = self.calculate()["close"]["nav"]
        path = self.prices / "closing_prices.csv"
        path.write_text(path.read_text().replace("225.00", "226.00"))
        self.assertEqual(self.calculate()["close"]["nav"], before - 3)

    def test_missing_stale_duplicate_wrong_currency_and_invalid_prices_fail(self):
        path = self.prices / "closing_prices.csv"
        original = path.read_text()
        cases = ["\n".join(original.splitlines()[:2]) + "\n",
                 original.replace("2025-01-09", "2025-01-08"),
                 original + "2025-01-09,AMZN.US,USD,225.00\n",
                 original.replace("USD", "GBP"), original.replace("225.00", "NaN")]
        for text in cases:
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    self.calculate()


if __name__ == "__main__":
    unittest.main()
