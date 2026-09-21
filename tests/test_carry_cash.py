import copy
from decimal import Decimal
from pathlib import Path
import shutil
import tempfile
import unittest

from carry_cash import carry_cash, roll_cash
from landing import land_delivery
from publication import approve, publish
import test_gbp_publication


class CarryCashTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.folder = self.root / "inputs"
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "daily_cash" / "2025-01-09"
        shutil.copytree(fixture, self.folder)
        self.opening = {"currency": "USD", "cash": "1000.00", "payables": "0", "receivables": "0",
                        "obligations": [], "known_execution_ids": ["OLD-SETTLED"]}

    def run_day(self):
        return roll_cash(self.opening, self.folder, "2025-01-08", "2025-01-09")

    def empty_day(self, day, confirmations=""):
        folder = self.root / day
        folder.mkdir()
        for name in ("executions.csv", "allocations.csv", "execution_terms.csv", "settlements.csv"):
            header = (self.folder / name).read_text().splitlines()[0]
            (folder / name).write_text(header + "\n" + (confirmations if name == "settlements.csv" else ""))
        return folder

    def test_trade_payable_and_duplicate_settlement_replay(self):
        original = copy.deepcopy(self.opening)
        first, second = self.run_day(), self.run_day()
        self.assertEqual(first, second)
        self.assertEqual(self.opening, original)
        self.assertEqual(first["cash"], Decimal("560"))
        self.assertEqual(first["payables"], Decimal("720"))
        self.assertEqual(first["repeated_settlements"], 1)
        self.assertEqual(len(first["cash_movements"]), 1)
        self.assertEqual(first["obligations"][0]["status"], "OPEN")

    def test_unpaid_obligation_survives_and_becomes_overdue(self):
        first = self.run_day()
        next_day = self.empty_day("2025-01-10")
        second = roll_cash(first, next_day, "2025-01-09", "2025-01-10")
        self.assertEqual(second["cash"], first["cash"])
        self.assertEqual(second["payables"], 720)
        self.assertEqual(second["obligations"][0]["status"], "OVERDUE")

    def test_yesterdays_payable_settles_once_and_then_replay_is_rejected(self):
        first = self.run_day()
        next_day = self.empty_day("2025-01-10",
            "2025-01-10,S3,SIM-D2-E001,USD,720.00,2025-01-10\n")
        second = roll_cash(first, next_day, "2025-01-09", "2025-01-10")
        self.assertEqual(second["cash"], -160)
        self.assertEqual(second["payables"], 0)
        self.assertEqual(second["obligations"], [])
        self.assertEqual(second["net_cash_and_obligations"], first["net_cash_and_obligations"])
        replay = self.empty_day("2025-01-13",
            "2025-01-13,S3,SIM-D2-E001,USD,720.00,2025-01-13\n")
        with self.assertRaisesRegex(ValueError, "already settled"):
            roll_cash(second, replay, "2025-01-10", "2025-01-13")
        self.assertEqual(second["cash"], -160)

    def test_yesterdays_receivable_increases_cash(self):
        self.opening["receivables"] = "50"
        self.opening["known_execution_ids"].append("OLD-SALE")
        self.opening["obligations"] = [{"execution_id": "OLD-SALE", "type": "RECEIVABLE",
                                        "amount": "50", "due": "2025-01-09", "status": "OPEN"}]
        folder = self.empty_day("2025-01-09", "2025-01-09,S4,OLD-SALE,USD,50.00,2025-01-09\n")
        result = roll_cash(self.opening, folder, "2025-01-08", "2025-01-09")
        self.assertEqual(result["cash"], 1050)
        self.assertEqual(result["receivables"], 0)

    def test_mismatches_future_settlement_and_double_confirmation_fail(self):
        path = self.folder / "settlements.csv"
        original = path.read_text()
        cases = [original.replace("440.00", "441.00"), original.replace(",USD,", ",GBP,"),
                 original.replace(",440.00,2025-01-09", ",440.00,2025-01-10"),
                 original + "2025-01-09,OTHER,SIM-D2-E002,USD,440.00,2025-01-09\n"]
        for content in cases:
            with self.subTest(content=content):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    self.run_day()
                self.assertEqual(self.opening["cash"], "1000.00")

    def test_reused_execution_and_inconsistent_opening_are_rejected(self):
        self.opening["known_execution_ids"].append("SIM-D2-E001")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_day()
        self.opening["known_execution_ids"].pop()
        self.opening["payables"] = "1"
        with self.assertRaisesRegex(ValueError, "obligation details"):
            self.run_day()

    def test_published_gbp_close_supplies_original_usd_cash(self):
        fixture = test_gbp_publication.GbpPublicationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        candidate = fixture.candidate()
        approve(fixture.db, candidate, "demo-reviewer", "Synthetic opening", 0)
        publish(fixture.db, candidate)
        delivery = land_delivery(self.folder, self.root / "landing", "2025-01-09", "daily_cash")
        result = carry_cash(fixture.db, "2025-01-08", delivery, "2025-01-09")
        self.assertEqual(result["cash_close"]["currency"], "USD")
        self.assertEqual(result["cash_close"]["cash"], 9560)
        self.assertEqual(result["opening_publication"]["candidate_id"], candidate)


if __name__ == "__main__":
    unittest.main()
