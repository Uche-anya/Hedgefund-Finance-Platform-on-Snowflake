import csv
import tempfile
import unittest
from pathlib import Path

from pipeline.prices import prepare


FIELDS = ("valuation_date", "universe_ticker", "currency", "close_price",
          "price_basis", "source_system")


class PriceDeliveryTests(unittest.TestCase):
    def write_prices(self, path, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def test_same_source_makes_same_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_file = root / "prices.csv"
            self.write_prices(csv_file, [
                dict(zip(FIELDS, ("2024-09-25", "AAPL", "USD", "226.37",
                                  "unadjusted", "massive"))),
                dict(zip(FIELDS, ("2024-09-25", "AMZN", "USD", "192.53",
                                  "unadjusted", "massive"))),
            ])
            first = prepare(csv_file, root, "2024-09-25")
            second = prepare(csv_file, root, "2024-09-25")
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(first["rows"], 2)
            self.assertEqual(first["file"].read_text().count("\n"), 2)

    def test_repeated_ticker_stops_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_file = root / "prices.csv"
            row = dict(zip(FIELDS, ("2024-09-25", "AAPL", "USD", "226.37",
                                    "unadjusted", "massive")))
            self.write_prices(csv_file, [row, row])
            with self.assertRaisesRegex(ValueError, "repeated ticker"):
                prepare(csv_file, root, "2024-09-25")


if __name__ == "__main__":
    unittest.main()
