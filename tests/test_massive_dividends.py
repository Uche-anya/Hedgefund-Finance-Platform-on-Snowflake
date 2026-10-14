import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.massive_dividends import get_pages, save_snapshot


class DividendSnapshotTests(unittest.TestCase):
    def event(self, amount="0.25"):
        return {"id": "event-1", "ticker": "AAPL", "ex_dividend_date": "2026-10-13",
                "cash_amount": amount, "currency": "USD", "pay_date": "2026-11-12"}

    def test_pagination_and_snapshot_retries(self):
        first = {"status": "OK", "results": [self.event()],
                 "next_url": "https://api.massive.com/stocks/v1/dividends?cursor=next"}
        second = {"status": "OK", "results": [], "next_url": None}
        with patch("pipeline.massive_dividends.request_page", side_effect=[first, second]) as request:
            pages = get_pages("2026-09-13", "2026-11-27", "test-key")
        self.assertEqual(request.call_count, 2)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = save_snapshot("2026-10-13", pages, root)
            self.assertEqual(folder, save_snapshot("2026-10-13", pages, root))
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["record_count"], 1)
            self.assertEqual(manifest["page_count"], 2)
            changed = [{"status": "OK", "results": [self.event("0.30")]}]
            corrected = save_snapshot("2026-10-13", changed, root)
            self.assertNotEqual(folder, corrected)
            self.assertTrue(folder.exists())

    def test_conflicting_event_ids_stop_the_snapshot(self):
        pages = [{"results": [self.event(), self.event("0.30")]}]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                save_snapshot("2026-10-13", pages, Path(temp))

    def test_empty_snapshot_is_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = save_snapshot("2026-10-13", [{"status": "OK", "results": []}], Path(temp))
            self.assertEqual((folder / "dividends.jsonl").read_text(encoding="utf-8"), "")


if __name__ == "__main__":
    unittest.main()
