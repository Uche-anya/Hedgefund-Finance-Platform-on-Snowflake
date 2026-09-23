import json
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from fund_pipeline.daily_close import calculate_close
from fund_pipeline.landing import land_delivery, verify_delivery


class LandingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / "source"
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14"
        shutil.copytree(fixture, self.source)
        self.landing = self.root / "landing"

    def land(self):
        return land_delivery(self.source, self.landing, "2026-09-14")

    def test_repeated_delivery_keeps_separate_evidence_and_same_nav(self):
        first, second = self.land(), self.land()
        self.assertNotEqual(first, second)
        for folder in (first, second):
            manifest = verify_delivery(folder, "2026-09-14")
            self.assertEqual(manifest["files"]["positions.csv"]["row_count"], 2)
            self.assertEqual(calculate_close(folder, "2026-09-14")["nav"], Decimal("10090"))
            for name in manifest["files"]:
                self.assertEqual((folder / name).read_bytes(), (self.source / name).read_bytes())

    def test_failed_copy_leaves_unusable_delivery(self):
        (self.source / "cash.csv").unlink()
        with self.assertRaises(FileNotFoundError):
            self.land()
        folder = next((self.landing / "2026-09-14").iterdir())
        with self.assertRaisesRegex(ValueError, "Incomplete delivery"):
            verify_delivery(folder, "2026-09-14")

    def test_changed_saved_file_is_rejected(self):
        folder = self.land()
        with (folder / "prices.csv").open("a") as file:
            file.write("2026-09-14,EXTRA,GBP,1.00\n")
        with self.assertRaisesRegex(ValueError, "Delivery file changed: prices.csv"):
            verify_delivery(folder, "2026-09-14")

    def test_correction_preserves_original_delivery(self):
        original = self.land()
        prices = self.source / "prices.csv"
        prices.write_text(prices.read_text().replace("18.00", "19.00"))
        corrected = self.land()
        verify_delivery(original, "2026-09-14")
        verify_delivery(corrected, "2026-09-14")
        self.assertEqual(calculate_close(original, "2026-09-14")["nav"], Decimal("10090"))
        self.assertEqual(calculate_close(corrected, "2026-09-14")["nav"], Decimal("10070"))

    def test_wrong_date_and_missing_manifest_entry_are_rejected(self):
        folder = self.land()
        with self.assertRaisesRegex(ValueError, "business date"):
            verify_delivery(folder, "2026-09-15")
        path = folder / "manifest.json"
        manifest = json.loads(path.read_text())
        del manifest["files"]["cash.csv"]
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "Manifest must list"):
            verify_delivery(folder, "2026-09-14")
