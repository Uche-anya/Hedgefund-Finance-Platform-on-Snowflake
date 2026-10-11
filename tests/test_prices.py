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

    def test_retry_ignores_request_id_but_stops_on_price_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_file = root / "prices.csv"
            fields = FIELDS + ("provider_request_id",)

            def write(close, request_id):
                with csv_file.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerow({
                        "valuation_date": "2024-09-25", "universe_ticker": "AAPL",
                        "currency": "USD", "close_price": close,
                        "price_basis": "unadjusted", "source_system": "massive",
                        "provider_request_id": request_id,
                    })

            write("226.370", "request-one")
            first = prepare(csv_file, root, "2024-09-25")
            write("226.37", "request-two")
            second = prepare(csv_file, root, "2024-09-25")
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(first["file"].read_bytes(), second["file"].read_bytes())

            write("226.38", "request-three")
            with self.assertRaisesRegex(ValueError, "differs from current input"):
                prepare(csv_file, root, "2024-09-25")


if __name__ == "__main__":
    unittest.main()
