import unittest
from datetime import datetime, timezone

from pipeline.schedule_day import scheduled_close


class ScheduleDayTest(unittest.TestCase):
    def test_weekend_and_market_holiday_are_skipped(self):
        self.assertIsNone(scheduled_close(
            datetime(2026, 10, 12, 4, 17, tzinfo=timezone.utc)))
        self.assertIsNone(scheduled_close(
            datetime(2026, 11, 27, 5, 17, tzinfo=timezone.utc)))

    def test_settlement_holiday_is_still_a_market_day(self):
        day = scheduled_close(
            datetime(2026, 10, 13, 4, 17, tzinfo=timezone.utc))
        self.assertEqual(day.isoformat(), "2026-10-12")

    def test_unreviewed_calendar_stops(self):
        with self.assertRaisesRegex(ValueError, "No reviewed US equity calendar"):
            scheduled_close(datetime(2027, 1, 5, 5, 17, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
