from decimal import Decimal
import shutil
import unittest

from fund_pipeline.carry_cash import carry_cash
from fund_pipeline.landing import land_delivery
from fund_pipeline.prepare_daily import prepare_daily
from fund_pipeline.publication import approve, current, publish, show
from fund_pipeline.reconcile_daily import make_mismatch
import test_reconcile_daily


class DailyPublicationTests(unittest.TestCase):
    def setUp(self):
        self.f = test_reconcile_daily.DailyReconciliationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.db = self.f.root / "daily_usd.sqlite"
        self.references = self.f.land_references()

    def prepare(self, references=None):
        return prepare_daily(self.db, self.f.db, "2025-01-08", self.f.activity,
                             self.f.prices, references or self.references, "2025-01-09")

    def publish_candidate(self, candidate, expected=0):
        approve(self.db, candidate, "demo-reviewer", "Synthetic daily close reviewed", expected)
        return publish(self.db, candidate)

    def test_review_then_publish_freezes_complete_close(self):
        candidate = self.prepare()
        with self.assertRaisesRegex(ValueError, "no recorded approval"):
            publish(self.db, candidate)
        self.assertEqual(self.publish_candidate(candidate), 1)
        close = current(self.db, "2025-01-09")["close"]
        self.assertEqual(Decimal(close["nav"]), 11350)
        self.assertEqual(len(close["known_execution_ids"]), 4)
        self.assertEqual(Decimal(close["payables"]), 720)
        self.assertEqual(publish(self.db, candidate), 1)

    def test_failed_position_blocks_both_approval_and_publication(self):
        wrong = make_mismatch(self.references, self.f.root / "landing", "2025-01-09")
        candidate = self.prepare(wrong)
        with self.assertRaisesRegex(ValueError, "reconciliation did not pass"):
            self.publish_candidate(candidate)
        with self.assertRaisesRegex(ValueError, "reconciliation did not pass"):
            publish(self.db, candidate)
        self.assertIsNone(show(self.db, candidate)["approval"])

    def test_next_day_settles_carried_payable_and_can_be_published(self):
        first = self.prepare()
        self.publish_candidate(first)
        source = self.f.root / "third_day"
        source.mkdir()
        for name in ("executions.csv", "allocations.csv", "execution_terms.csv", "settlements.csv"):
            header = (self.f.activity / name).read_text().splitlines()[0]
            (source / name).write_text(header + "\n")
        with (source / "settlements.csv").open("a") as file:
            file.write("2025-01-10,S3,SIM-D2-E001,USD,720.00,2025-01-10\n")
        activity = land_delivery(source, self.f.root / "landing", "2025-01-10", "daily_cash")
        prices = self.f.root / "third_prices"
        shutil.copytree(self.f.prices, prices)
        path = prices / "closing_prices.csv"
        path.write_text(path.read_text().replace("2025-01-09", "2025-01-10"))
        price_delivery = land_delivery(prices, self.f.root / "landing", "2025-01-10", "daily_prices")
        references = self.f.root / "third_references"
        shutil.copytree(self.references, references)
        for path in references.glob("*.csv"):
            text = path.read_text().replace("2025-01-09", "2025-01-10").replace("9560.00", "8840.00")
            if path.name == "open_obligations.csv":
                text = text.splitlines()[0] + "\n"
            path.write_text(text)
        reference_delivery = land_delivery(references, self.f.root / "landing", "2025-01-10", "daily_references")
        # A daily publication must work even when its prior activity folder is unavailable.
        # Its complete history was frozen in the candidate, not rebuilt from that folder.
        shutil.rmtree(self.f.activity)
        third = prepare_daily(self.db, self.db, "2025-01-09", activity, price_delivery,
                              reference_delivery, "2025-01-10")
        self.publish_candidate(third)
        close = current(self.db, "2025-01-10")["close"]
        self.assertEqual(Decimal(close["cash"]), 8840)
        self.assertEqual(Decimal(close["payables"]), 0)
        self.assertEqual(Decimal(close["nav"]), 11350)
        self.assertEqual(len(close["known_execution_ids"]), 4)
        # Old execution IDs cannot re-enter on a later day.
        (source / "executions.csv").write_text(
            "business_date,execution_id,instrument,side,quantity\n2025-01-10,SIM-E001,AAPL.US,BUY,1\n")
        (source / "allocations.csv").write_text(
            "business_date,allocation_id,execution_id,portfolio,quantity\n2025-01-10,A3,SIM-E001,GROWTH,1\n")
        (source / "execution_terms.csv").write_text(
            "business_date,execution_id,currency,execution_price,settlement_due\n2025-01-10,SIM-E001,USD,245,2025-01-11\n")
        replay = land_delivery(source, self.f.root / "landing", "2025-01-10", "daily_cash")
        with self.assertRaisesRegex(ValueError, "already exists"):
            carry_cash(self.db, "2025-01-09", replay, "2025-01-10")

    def test_review_uses_frozen_evidence_and_versions_remain_immutable(self):
        first, second = self.prepare(), self.prepare()
        self.publish_candidate(first)
        frozen = show(self.db, first)["candidate"]
        (self.references / "broker_positions.csv").write_text("changed file")
        self.assertEqual(self.publish_candidate(second, 1), 2)
        self.assertEqual(show(self.db, first)["candidate"], frozen)
        self.assertEqual(publish(self.db, first), 1)
        self.assertEqual(current(self.db, "2025-01-09")["publication"]["version"], 2)

    def test_cannot_store_usd_candidate_in_gbp_database(self):
        self.db = self.f.db
        with self.assertRaisesRegex(ValueError, "separate USD"):
            self.prepare()


if __name__ == "__main__":
    unittest.main()
