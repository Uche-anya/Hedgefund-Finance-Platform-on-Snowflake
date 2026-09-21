import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from landing import land_delivery
from publication import approve, publish, show
from run_pipeline import run_pipeline
from run_config import read_config
import test_gbp_publication


class PipelineTests(unittest.TestCase):
    def setUp(self):
        # Reuse the synthetic deliveries from the GBP lesson.
        self.fixture = test_gbp_publication.GbpPublicationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture

    def run_close(self, fx=None, reference=None, as_of="2025-01-08"):
        return run_pipeline(self.f.nav, self.f.usd, fx or self.f.fx,
                            reference or self.f.reference, "2025-01-06", as_of,
                            self.f.db, self.f.root / "runs")

    def test_success_records_inputs_and_leaves_candidate_unapproved(self):
        result = self.run_close()
        self.assertEqual(result["status"], "READY_FOR_REVIEW")
        self.assertEqual(len(result["manifest_sha256"]), 4)
        self.assertEqual(len(result["controls"]), 7)
        self.assertEqual(json.loads(Path(result["run_record"]).read_text()), result)
        candidate = show(self.f.db, result["candidate_id"])
        self.assertIsNone(candidate["approval"])
        self.assertIsNone(candidate["publication"])

    def test_rerun_keeps_both_attempts_without_publishing(self):
        first, second = self.run_close(), self.run_close()
        self.assertNotEqual(first["run_id"], second["run_id"])
        self.assertEqual(first["candidate_id"], second["candidate_id"])
        self.assertFalse(first["candidate_reused"])
        self.assertTrue(second["candidate_reused"])
        self.assertTrue(Path(first["run_record"]).exists())
        with sqlite3.connect(self.f.db) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM candidates").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM publications").fetchone()[0], 0)

    def test_missing_fx_records_failure_without_candidate(self):
        result = self.run_close(fx=self.f.root / "missing_fx")
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["stage"], "check_inputs")
        self.assertIsNone(result["candidate_id"])
        self.assertIn("FX", result["error"]["message"])
        self.assertFalse(self.f.db.exists())

    def test_failed_control_retains_candidate_for_investigation(self):
        source = self.f.root / "bad_reference"
        source.mkdir()
        path = self.f.reference / "gbp_reference.csv"
        (source / path.name).write_text(path.read_text().replace(",nav,8000", ",nav,9000"))
        provenance = json.loads((self.f.reference / "manifest.json").read_text())["provenance"]
        reference = land_delivery(source, self.f.root / "landing", "2025-01-08",
                                  "gbp_references", provenance=provenance)
        result = self.run_close(reference=reference)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["stage"], "check_candidate")
        self.assertTrue(any(row["status"] == "FAIL" for row in result["controls"]))
        self.assertIsNone(show(self.f.db, result["candidate_id"])["approval"])
        retry = self.run_close(reference=reference)
        self.assertEqual(retry["status"], "FAILED")
        self.assertFalse(retry["candidate_reused"])
        self.assertNotEqual(retry["candidate_id"], result["candidate_id"])

    def test_changed_fx_and_reference_create_new_candidate(self):
        first = self.run_close()
        from test_fx_reporting import synthetic_ecb
        fx, reference = self.f.new_fx(synthetic_ecb().replace(b"1.00,GBP", b"0.90,GBP"))
        second = self.run_close(fx=fx, reference=reference)
        self.assertEqual(second["status"], "READY_FOR_REVIEW")
        self.assertFalse(second["candidate_reused"])
        self.assertNotEqual(first["candidate_id"], second["candidate_id"])
        self.assertNotEqual(first["input_key"], second["input_key"])

    def test_changed_calculation_code_creates_new_candidate(self):
        first = self.run_close()
        original = Path.read_bytes
        def changed(path):
            content = original(path)
            return content + b"\n# simulated code revision\n" if path.name == "fund_nav.py" else content
        with patch.object(Path, "read_bytes", changed):
            second = self.run_close()
        self.assertFalse(second["candidate_reused"])
        self.assertNotEqual(first["candidate_id"], second["candidate_id"])

    def test_tampered_input_is_not_hidden_by_reuse(self):
        self.run_close()
        (self.f.fx / "usd_gbp.csv").write_text("corrupt")
        result = self.run_close()
        self.assertEqual(result["status"], "FAILED")
        self.assertIsNone(result["candidate_id"])

    def test_overlapping_runs_share_one_candidate(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.run_close(), range(2)))
        self.assertTrue(all(row["status"] == "READY_FOR_REVIEW" for row in results), results)
        self.assertEqual(len({row["candidate_id"] for row in results}), 1)
        self.assertEqual(sorted(row["candidate_reused"] for row in results), [False, True])

    def test_missing_run_log_does_not_lose_reuse_registration(self):
        first = self.run_close()
        Path(first["run_record"]).unlink()
        second = self.run_close()
        self.assertTrue(second["candidate_reused"])
        self.assertEqual(first["candidate_id"], second["candidate_id"])

    def test_reuse_reports_approval_and_publication_without_changing_them(self):
        first = self.run_close()
        approve(self.f.db, first["candidate_id"], "demo-reviewer", "Synthetic test", 0)
        approved = self.run_close()
        self.assertEqual(approved["status"], "ALREADY_APPROVED")
        publish(self.f.db, first["candidate_id"])
        published = self.run_close()
        self.assertEqual(published["status"], "ALREADY_PUBLISHED")
        self.assertEqual(published["publication"]["version"], 1)
        self.assertEqual(published["candidate_id"], first["candidate_id"])

    def test_reuse_is_scoped_to_database(self):
        first = self.run_close()
        self.f.db = self.f.root / "other.sqlite"
        second = self.run_close()
        self.assertFalse(second["candidate_reused"])
        self.assertNotEqual(first["candidate_id"], second["candidate_id"])

    def test_bad_date_is_recorded(self):
        result = self.run_close(as_of="not-a-date")
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["error"]["type"], "ValueError")

    def config_file(self):
        settings = {"business_date": "2025-01-06", "as_of": "2025-01-08",
                    "delivery": str(self.f.nav.relative_to(self.f.root)),
                    "references": str(self.f.usd.relative_to(self.f.root)),
                    "fx_delivery": str(self.f.fx.relative_to(self.f.root)),
                    "gbp_references": str(self.f.reference.relative_to(self.f.root)),
                    "database": "gbp.sqlite", "run_root": "runs"}
        path = self.f.root / "close.json"
        path.write_text(json.dumps(settings), encoding="utf-8")
        return path

    def test_config_runs_from_another_folder_and_reuses_same_candidate(self):
        first = self.run_close()
        config = self.config_file()
        script = Path(__file__).resolve().parents[1] / "run_pipeline.py"
        other_folder = self.f.root / "another_folder"
        other_folder.mkdir()
        result = subprocess.run([sys.executable, str(script), "--config", str(config)],
                                cwd=other_folder, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(first["candidate_id"], result.stdout)
        self.assertIn("Reused existing candidate", result.stdout)
        records = [json.loads(path.read_text()) for path in (self.f.root / "runs").glob("*.json")]
        configured = next(row for row in records if "configuration" in row)
        self.assertEqual(configured["configuration"]["path"], str(config.resolve()))
        self.assertEqual(configured["inputs"]["nav"], str(self.f.nav.resolve()))

    def test_config_rejects_typos_duplicates_and_invalid_values(self):
        path = self.config_file()
        valid = json.loads(path.read_text())
        cases = [{**valid, "asof": "2025-01-08"}, {**valid, "delivery": ""},
                 {**valid, "as_of": "2025-01-05"}, {**valid, "as_of": "20250108"},
                 {**valid, "database": 42}, []]
        for settings in cases:
            with self.subTest(settings=settings):
                path.write_text(json.dumps(settings))
                with self.assertRaises(ValueError):
                    read_config(path)
        path.write_text('{"as_of":"2025-01-08","as_of":"2025-01-09"}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            read_config(path)

    def test_config_cannot_be_mixed_with_command_line_dates(self):
        config = self.config_file()
        script = Path(__file__).resolve().parents[1] / "run_pipeline.py"
        result = subprocess.run([sys.executable, str(script), "--config", str(config),
                                 "--as-of", "2025-01-09"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("do not mix", result.stderr)
        self.assertFalse(self.f.db.exists())

    def test_cli_success_and_failure_exit_codes(self):
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "run_pipeline.py"),
                   "--delivery", str(self.f.nav), "--references", str(self.f.usd),
                   "--gbp-references", str(self.f.reference), "--business-date", "2025-01-06",
                   "--as-of", "2025-01-08", "--database", str(self.f.db),
                   "--run-root", str(self.f.root / "runs"), "--fx-delivery", str(self.f.fx)]
        success = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(success.returncode, 0, success.stderr)
        self.assertIn("READY_FOR_REVIEW", success.stdout)
        command[-1] = str(self.f.root / "missing")
        failure = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(failure.returncode, 1, failure.stderr)
        self.assertIn("Stopped at check_inputs", failure.stdout)


if __name__ == "__main__":
    unittest.main()
