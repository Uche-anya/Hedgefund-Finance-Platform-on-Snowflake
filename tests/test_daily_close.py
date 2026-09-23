import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from fund_pipeline.daily_close import calculate_close


class DailyCloseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "inputs"
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14"
        shutil.copytree(fixture, self.folder)

    def test_hand_worked_long_and_short(self):
        result = calculate_close(self.folder, "2026-09-14")
        values = {row["instrument"]: row["market_value"] for row in result["holdings"]}
        self.assertEqual(values, {"ALPHA": Decimal("1050"), "BETA": Decimal("-360")})
        self.assertEqual(result["cash"], Decimal("9400"))
        self.assertEqual(result["nav"], Decimal("10090"))

    def test_missing_short_price_stops_close(self):
        path = self.folder / "prices.csv"
        lines = path.read_text().splitlines()
        path.write_text("\n".join(lines[:2]) + "\n")
        with self.assertRaisesRegex(ValueError, "Missing price for BETA"):
            calculate_close(self.folder, "2026-09-14")

    def test_duplicate_price_stops_close(self):
        path = self.folder / "prices.csv"
        with path.open("a") as file:
            file.write("2026-09-14,ALPHA,GBP,10.50\n")
        with self.assertRaisesRegex(ValueError, "Duplicate price"):
            calculate_close(self.folder, "2026-09-14")

    def test_duplicate_position_stops_close(self):
        path = self.folder / "positions.csv"
        with path.open("a") as file:
            file.write("2026-09-14,GROWTH,ALPHA,100\n")
        with self.assertRaisesRegex(ValueError, "Duplicate position"):
            calculate_close(self.folder, "2026-09-14")

    def test_wrong_business_date_stops_close(self):
        with self.assertRaisesRegex(ValueError, "expected business date"):
            calculate_close(self.folder, "2026-09-15")
