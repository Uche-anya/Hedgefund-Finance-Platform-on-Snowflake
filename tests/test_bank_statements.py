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

    def test_ledger_rolls_forward_and_fee_creates_a_real_difference(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            statement = root / "bank.csv"
            statement.write_text(
                'account_id,currency,opening_balance,closing_balance,postings_json\n'
                'ACCOUNT-1,USD,100.00,45.00,'
                '"[{""posting_id"":""SETTLEMENT-1"",""posting_date"":""2026-10-16"",'
                '""amount"":""-25.00"",""type"":""TRADE_SETTLEMENT""},'
                '{""posting_id"":""FEE-1"",""posting_date"":""2026-10-16"",'
                '""amount"":""-30.00"",""type"":""BANK_FEE""}]"\n',
                encoding="utf-8")
            item = prepare(statement, root, "2026-10-16", "SCENARIO",
                           previous_date="2026-10-15")
            self.assertEqual(item["rows"], 1)
            statement.write_text(statement.read_text(encoding="utf-8").replace(
                "45.00", "95.00"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "roll forward"):
                prepare(statement, root, "2026-10-16", "SCENARIO",
                        previous_date="2026-10-15")


if __name__ == "__main__":
    unittest.main()
