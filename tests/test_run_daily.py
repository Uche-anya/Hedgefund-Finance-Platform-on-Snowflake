from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from fund_pipeline.publication import approve, publish, show
from fund_pipeline.reconcile_daily import make_mismatch
from fund_pipeline.run_daily import read_daily_config, run_daily
import test_daily_publication


class DailyRunnerTests(unittest.TestCase):
    def setUp(self):
        self.f = test_daily_publication.DailyPublicationTests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.settings = {"database": self.f.db, "opening_database": self.f.f.db,
                         "previous_date": "2025-01-08", "business_date": "2025-01-09",
                         "delivery": self.f.f.activity, "prices": self.f.f.prices,
                         "references": self.f.references, "run_root": self.f.f.root / "runs"}

    def test_retry_reuses_candidate_and_preserves_both_run_records(self):
        first, second = run_daily(self.settings), run_daily(self.settings)
        self.assertEqual(first["status"], "READY_FOR_REVIEW")
        self.assertEqual(first["candidate_id"], second["candidate_id"])
        self.assertFalse(first["candidate_reused"])
        self.assertTrue(second["candidate_reused"])
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertIsNone(show(self.f.db, first["candidate_id"])["approval"])
        self.assertEqual(json.loads(Path(second["run_record"]).read_text()), second)

    def test_republished_opening_forces_a_new_candidate(self):
        first = run_daily(self.settings)
        opening_fixture = self.f.f.fixture.f
        replacement = opening_fixture.candidate()
        approve(self.f.f.db, replacement, "demo-reviewer", "Synthetic opening revision", 1)
        publish(self.f.f.db, replacement)
        second = run_daily(self.settings)
        self.assertEqual(second["status"], "READY_FOR_REVIEW")
        self.assertNotEqual(first["candidate_id"], second["candidate_id"])
        self.assertEqual(second["opening_publication"]["version"], 2)

    def test_mismatch_and_missing_inputs_are_failed_runs(self):
        wrong = make_mismatch(self.f.references, self.f.f.root / "landing", "2025-01-09")
        result = run_daily({**self.settings, "references": wrong})
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["stage"], "check_candidate")
        self.assertIsNotNone(result["candidate_id"])
        missing = run_daily({**self.settings, "prices": self.f.f.root / "missing"})
        self.assertEqual(missing["status"], "FAILED")
        self.assertIsNone(missing["candidate_id"])

    def test_overlapping_runs_save_one_successful_candidate(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: run_daily(self.settings), range(2)))
        self.assertTrue(all(row["status"] == "READY_FOR_REVIEW" for row in results), results)
        self.assertEqual(len({row["candidate_id"] for row in results}), 1)
        self.assertEqual(sorted(row["candidate_reused"] for row in results), [False, True])

    def test_changed_financial_code_creates_new_candidate(self):
        first = run_daily(self.settings)
        original = Path.read_bytes
        def revised(path):
            content = original(path)
            return content + b"\n# test revision" if path.name == "daily_nav.py" else content
        with patch.object(Path, "read_bytes", revised):
            second = run_daily(self.settings)
        self.assertEqual(second["status"], "READY_FOR_REVIEW")
        self.assertNotEqual(first["candidate_id"], second["candidate_id"])

    def test_published_candidate_is_reported_without_republishing(self):
        first = run_daily(self.settings)
        approve(self.f.db, first["candidate_id"], "demo-reviewer", "Synthetic review", 0)
        publish(self.f.db, first["candidate_id"])
        second = run_daily(self.settings)
        self.assertEqual(second["status"], "ALREADY_PUBLISHED")
        self.assertEqual(second["publication"]["version"], 1)

    def test_configuration_and_cli_from_another_folder(self):
        root = self.f.f.root
        config = root / "daily.json"
        values = {name: str(value.relative_to(root)) if isinstance(value, Path) else value
                  for name, value in self.settings.items()}
        config.write_text(json.dumps(values))
        resolved, _ = read_daily_config(config)
        self.assertEqual(resolved["delivery"], self.settings["delivery"])
        other = root / "elsewhere"
        other.mkdir()
        result = subprocess.run([sys.executable, "-m", "fund_pipeline.run_daily", "--config", str(config)],
                                cwd=other, capture_output=True, text=True,
                                env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("READY_FOR_REVIEW", result.stdout)
        config.write_text(json.dumps({**values, "business_date": "2025-01-11"}))
        with self.assertRaisesRegex(ValueError, "consecutive"):
            read_daily_config(config)
        config.write_text('{"previous_date":"2025-01-08","previous_date":"2025-01-09"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            read_daily_config(config)


if __name__ == "__main__":
    unittest.main()
