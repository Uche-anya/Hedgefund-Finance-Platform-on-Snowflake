import unittest
from unittest.mock import patch

from pipeline.produce_bank import balances


class Cursor:
    def __init__(self, paid_dividends=0):
        self.paid_dividends = paid_dividends
        self.query_number = 0

    def execute(self, statement, params):
        self.query_number += 1

    def fetchall(self):
        if self.query_number == 1:
            return [("ACCOUNT-1", "USD", "100.00")]
        return [("EXEC-1", "ACCOUNT-1", "BUY", "2", "12.50", "USD")]

    def fetchone(self):
        return (self.paid_dividends,)


class BankProducerTests(unittest.TestCase):
    @patch("pipeline.produce_bank.check_source", return_value=(True, "ready"))
    def test_due_trade_reduces_bank_cash(self, _):
        cash = balances(Cursor(), "2026-10-16", "2026-10-07", "SCENARIO")
        self.assertEqual(str(cash["ACCOUNT-1"]), "75.00")

    @patch("pipeline.produce_bank.check_source", return_value=(True, "ready"))
    def test_paid_dividend_stops_without_bank_payment_evidence(self, _):
        with self.assertRaisesRegex(ValueError, "Dividend payment evidence"):
            balances(Cursor(paid_dividends=1), "2026-10-16", "2026-10-07", "SCENARIO")


if __name__ == "__main__":
    unittest.main()
