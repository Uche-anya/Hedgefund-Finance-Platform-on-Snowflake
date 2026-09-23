import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fund_pipeline.business_calendar import read_calendar, validate_close_dates
from fund_pipeline.carry_cash import roll_cash
from fund_pipeline.run_daily import run_daily, read_daily_config
import test_run_daily


CALENDAR = Path(__file__).resolve().parents[1] / "calendars" / "us_equities_2025_01_v1.json"


class ExchangeCalendarTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.calendar = read_calendar(CALENDAR, hashlib.sha256(CALENDAR.read_bytes()).hexdigest())

    def test_regular_holiday_and_exceptional_closure(self):
        validate_close_dates("2025-01-17", "2025-01-21", self.calendar)
        validate_close_dates("2025-01-08", "2025-01-10", self.calendar)
        for previous, today in (("2025-01-17", "2025-01-20"), ("2025-01-08", "2025-01-09"),
                                 ("2025-01-09", "2025-01-10")):
            with self.subTest(previous=previous, today=today):
                with self.assertRaisesRegex(ValueError, "both be open"):
                    validate_close_dates(previous, today, self.calendar)

    def test_unknown_range_and_skipped_open_day_fail(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            validate_close_dates("2025-01-31", "2025-02-03", self.calendar)
        with self.assertRaisesRegex(ValueError, "do not skip"):
            validate_close_dates("2025-01-13", "2025-01-15", self.calendar)

    def test_pinned_hash_and_complete_date_coverage(self):
        path = self.root / "calendar.json"
        raw = CALENDAR.read_bytes()
        path.write_bytes(raw + b"\n")
        with self.assertRaisesRegex(ValueError, "fingerprint changed"):
            read_calendar(path, hashlib.sha256(raw).hexdigest())
        for mutation in ("missing", "duplicate", "bad_boolean"):
            data = copy.deepcopy(self.calendar["snapshot"])
            if mutation == "missing":
                data["days"].pop(2)
            elif mutation == "duplicate":
                data["days"].insert(2, data["days"][1])
            else:
                data["days"][1]["is_open"] = "false"
            path.write_text(json.dumps(data))
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    read_calendar(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_market_holiday_does_not_decide_if_payment_settled(self):
        fixture = CALENDAR.parents[1] / "fixtures" / "daily_cash" / "2025-01-10"
        for name in ("executions.csv", "allocations.csv", "execution_terms.csv", "settlements.csv"):
            (self.root / name).write_text((fixture / name).read_text().splitlines()[0] + "\n")
        opening = {"currency": "USD", "cash": "1000", "payables": "100", "receivables": "0",
                   "known_execution_ids": ["OLD"], "obligations": [
                       {"execution_id": "OLD", "type": "PAYABLE", "amount": "100", "due": "2025-01-21"}]}
        unpaid = roll_cash(opening, self.root, "2025-01-17", "2025-01-21", self.calendar)
        self.assertEqual(unpaid["cash"], 1000)
        self.assertEqual(unpaid["payables"], 100)
        with (self.root / "settlements.csv").open("a") as file:
            file.write("2025-01-21,S1,OLD,USD,100,2025-01-20\n")
        paid = roll_cash(opening, self.root, "2025-01-17", "2025-01-21", self.calendar)
        self.assertEqual(paid["cash"], 900)
        self.assertEqual(paid["payables"], 0)
        self.assertEqual(paid["cash_movements"][0]["settled_on"], "2025-01-20")

    def test_config_pins_calendar_and_rejects_closed_valuation(self):
        config_path = CALENDAR.parents[1] / "configs" / "daily_usd_2025-01-13_exchange_calendar.json"
        settings, _ = read_daily_config(config_path)
        self.assertEqual(settings["calendar"], CALENDAR)
        raw = json.loads(config_path.read_text())
        raw["calendar"] = str(CALENDAR)
        raw.update(previous_date="2025-01-17", business_date="2025-01-20")
        path = self.root / "config.json"
        path.write_text(json.dumps(raw))
        with self.assertRaisesRegex(ValueError, "both be open"):
            read_daily_config(path)

    def test_calendar_revision_changes_reuse_key_and_freezes_snapshot(self):
        fixture = test_run_daily.DailyRunnerTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        # These tests use the old simulated Jan 9 close. Explicitly make a
        # synthetic test calendar; do not alter the sourced calendar on disk.
        data = copy.deepcopy(self.calendar["snapshot"])
        data.update(calendar_id="SYNTHETIC_TEST_CALENDAR", sources=["https://example.test/calendar"])
        next(row for row in data["days"] if row["date"] == "2025-01-09").update(
            is_open=True, reason="Synthetic test date, not an actual market session")
        path = self.root / "test_calendar.json"
        path.write_text(json.dumps(data))
        settings = {**fixture.settings, "calendar": path, "calendar_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        first = run_daily(settings)
        self.assertEqual(first["status"], "READY_FOR_REVIEW")
        self.assertTrue(run_daily(settings)["candidate_reused"])
        data["version"] = "synthetic-test-v2"
        path.write_text(json.dumps(data))
        failed = run_daily(settings)
        self.assertEqual(failed["status"], "FAILED")
        self.assertIsNone(failed["candidate_id"])
        settings["calendar_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        second = run_daily(settings)
        self.assertEqual(second["status"], "READY_FOR_REVIEW")
        self.assertNotEqual(first["candidate_id"], second["candidate_id"])
        from fund_pipeline.publication import show
        stored = show(settings["database"], first["candidate_id"])["candidate"]["reconciliation"]["calendar"]
        self.assertEqual(stored["snapshot"]["version"], "project-v1")


if __name__ == "__main__":
    unittest.main()
