import unittest
from unittest.mock import patch

from pipeline.produce_bank import ledger


class Cursor:
    def __init__(self, paid_dividends=0, previous=None):
        self.paid_dividends = paid_dividends
        self.previous = previous
        self.statement = ""
        self.statements = []

    def execute(self, statement, params):
        self.statement = statement
        self.statements.append(statement)

    def fetchall(self):
        if "DAILY_OMS_EVENTS" not in self.statement:
            return [("ACCOUNT-1", "USD", "100.00"),
                    ("ACCOUNT-2", "USD", "200.00")]
        return [("EXEC-1", "ACCOUNT-1", "BUY", "2", "12.50", "USD",
                 "2026-10-16")]

    def fetchone(self):
        if "MAX(business_date)" in self.statement:
            return (self.previous,)
        if "DAILY_CLOSE_RUNS" in self.statement:
            return (1,)
        return (self.paid_dividends,)


class BankProducerTests(unittest.TestCase):
    @patch("pipeline.produce_bank.check_source", return_value=(True, "ready"))
    def test_due_trade_reduces_bank_cash(self, _):
        cursor = Cursor()
        start, accounts = ledger(cursor, "2026-10-16", "2026-10-07", "SCENARIO")
        self.assertEqual(start, "2026-10-07")
        self.assertEqual(str(accounts["ACCOUNT-1"]["closing_balance"]), "75.00")
        self.assertEqual(accounts["ACCOUNT-2"]["postings"], [])
        self.assertFalse(any("FCT_DIVIDEND_EXPOSURE" in sql for sql in cursor.statements))

    @patch("pipeline.produce_bank.check_source", return_value=(True, "ready"))
    def test_paid_dividend_stops_without_bank_payment_evidence(self, _):
        with self.assertRaisesRegex(ValueError, "Dividend payment evidence"):
            ledger(Cursor(paid_dividends=1, previous="2026-10-15"),
                   "2026-10-16", "2026-10-07", "SCENARIO")

    @patch("pipeline.produce_bank.check_source", return_value=(True, "ready"))
    def test_missing_previous_market_day_stops(self, _):
        with self.assertRaisesRegex(ValueError, "Previous market day"):
            ledger(Cursor(previous="2026-10-14"), "2026-10-16",
                   "2026-10-07", "SCENARIO")

    @patch("pipeline.produce_bank.check_source", return_value=(True, "ready"))
    def test_next_day_uses_previous_bank_balance(self, _):
        start, accounts = ledger(Cursor(previous="2026-10-15"),
                                 "2026-10-16", "2026-10-07", "SCENARIO")
        self.assertEqual(start, "2026-10-15")
        self.assertEqual(str(accounts["ACCOUNT-1"]["closing_balance"]), "75.00")


if __name__ == "__main__":
    unittest.main()
