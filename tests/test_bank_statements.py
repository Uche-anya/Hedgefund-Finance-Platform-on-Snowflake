import csv
import tempfile
import unittest
from pathlib import Path

from pipeline.bank_statements import prepare


class BankStatementTests(unittest.TestCase):
    def test_retry_keeps_the_same_delivery_and_changed_balance_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            statement = root / "bank.csv"

            def write(balance):
                with statement.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(("account_id", "currency", "closing_balance"))
                    writer.writerow(("SIM-ACCOUNT-01", "USD", balance))

            write("4994888.65")
            first = prepare(statement, root, "2026-10-16", "sim-close-20261008")
            second = prepare(statement, root, "2026-10-16", "sim-close-20261008")
            self.assertEqual(first["id"], second["id"])

            write("4994888.64")
            with self.assertRaisesRegex(ValueError, "differs"):
                prepare(statement, root, "2026-10-16", "sim-close-20261008")

    def test_repeated_account_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            statement = root / "bank.csv"
            statement.write_text(
                "account_id,currency,closing_balance\n"
                "SIM-ACCOUNT-01,USD,1.00\n"
                "SIM-ACCOUNT-01,USD,2.00\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Repeated account"):
                prepare(statement, root, "2026-10-16", "sim-close-20261008")


if __name__ == "__main__":
    unittest.main()
