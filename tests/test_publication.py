from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from landing import land_delivery
from publication import approve, current, database, prepare, publish, show
from reconcile import make_demo_delivery


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.repo = Path(__file__).resolve().parents[1]
        self.db = self.root / "publication.sqlite"
        self.source = self.root / "source"
        self.refs = self.root / "references"
        shutil.copytree(self.repo / "fixtures" / "settlement" / "2026-09-14", self.source)
        shutil.copytree(self.repo / "fixtures" / "references" / "2026-09-16", self.refs)
        self.nav = land_delivery(self.source, self.root / "landing", "2026-09-14", "nav")
        self.reference = land_delivery(self.refs, self.root / "landing", "2026-09-16", "references")

    def candidate(self, nav=None, reference=None):
        return prepare(self.db, nav or self.nav, reference or self.reference, "2026-09-14", "2026-09-16")

    def approve(self, candidate, version=0):
        approve(self.db, candidate, "demo-reviewer", "Reviewed synthetic close and all comparisons", version)

    def test_passing_candidate_requires_explicit_approval_then_publishes(self):
        candidate = self.candidate()
        with self.assertRaisesRegex(ValueError, "No published close"):
            current(self.db, "2026-09-16")
        with self.assertRaisesRegex(ValueError, "no recorded approval"):
            publish(self.db, candidate)
        self.approve(candidate)
        self.assertEqual(publish(self.db, candidate), 1)
        published = current(self.db, "2026-09-16")
        self.assertEqual(published["close"]["nav"], "10105.00")
        self.assertEqual(published["approval"]["reviewer"], "demo-reviewer")
        self.assertTrue(published["approval"]["approved_at"])

    def test_69_share_failure_cannot_be_approved_or_published(self):
        reference = make_demo_delivery(self.reference, self.root / "landing", "2026-09-16")
        candidate = self.candidate(reference=reference)
        self.assertEqual(show(self.db, candidate)["candidate"]["reconciliation"]["status"], "FAIL")
        with self.assertRaisesRegex(ValueError, "reconciliation did not pass"):
            self.approve(candidate)
        with self.assertRaisesRegex(ValueError, "reconciliation did not pass"):
            publish(self.db, candidate)
        self.assertIsNone(show(self.db, candidate)["approval"])

    def test_blank_reviewer_or_note_cannot_approve(self):
        candidate = self.candidate()
        for reviewer, note in ((" ", "checked"), ("demo-reviewer", " ")):
            with self.subTest(reviewer=reviewer):
                with self.assertRaises(ValueError):
                    approve(self.db, candidate, reviewer, note, 0)

    def test_correction_creates_new_version_and_preserves_old_close(self):
        original = self.candidate()
        self.approve(original)
        publish(self.db, original)
        old = show(self.db, original)
        prices = self.source / "closing_prices.csv"
        prices.write_text(prices.read_text().replace("2026-09-16,BETA,GBP,18.00", "2026-09-16,BETA,GBP,19.00"))
        # Separate hand-worked corrected expectation: NAV falls by GBP 20.
        nav_reference = self.refs / "administrator_nav.csv"
        nav_reference.write_text(nav_reference.read_text().replace("10105.00", "10085.00"))
        nav = land_delivery(self.source, self.root / "landing", "2026-09-14", "nav")
        refs = land_delivery(self.refs, self.root / "landing", "2026-09-16", "references")
        corrected = self.candidate(nav, refs)
        self.assertEqual(current(self.db, "2026-09-16")["close"]["nav"], "10105.00")
        self.approve(corrected, 1)
        self.assertEqual(publish(self.db, corrected), 2)
        self.assertEqual(current(self.db, "2026-09-16")["close"]["nav"], "10085.00")
        self.assertEqual(show(self.db, original)["candidate"], old["candidate"])
        self.assertEqual(show(self.db, original)["publication"], old["publication"])
        self.assertEqual(publish(self.db, original), 1)
        self.assertEqual(current(self.db, "2026-09-16")["publication"]["version"], 2)

    def test_publication_retry_does_not_create_another_version(self):
        candidate = self.candidate()
        self.approve(candidate)
        self.assertEqual(publish(self.db, candidate), 1)
        self.assertEqual(publish(self.db, candidate), 1)
        with database(self.db) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM publications").fetchone()[0], 1)

    def test_competing_approvals_cannot_overwrite_newer_publication(self):
        first, second = self.candidate(), self.candidate()
        self.approve(first)
        self.approve(second)
        def attempt(candidate):
            try:
                return publish(self.db, candidate)
            except ValueError as error:
                return str(error)
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(attempt, (first, second)))
        self.assertEqual(results.count(1), 1)
        self.assertTrue(any("Stale approval" in str(result) for result in results))
        self.assertEqual(current(self.db, "2026-09-16")["publication"]["version"], 1)

    def test_stale_review_version_cannot_be_approved(self):
        first, second = self.candidate(), self.candidate()
        self.approve(first)
        publish(self.db, first)
        with self.assertRaisesRegex(ValueError, "Published version changed"):
            self.approve(second, 0)

    def test_saved_history_rejects_update_and_delete(self):
        candidate = self.candidate()
        self.approve(candidate)
        publish(self.db, candidate)
        for table in ("candidates", "approvals", "publications"):
            for statement in (f"DELETE FROM {table}", f"UPDATE {table} SET rowid = rowid"):
                with self.subTest(statement=statement):
                    with self.assertRaisesRegex(sqlite3.IntegrityError, "History is immutable"):
                        with database(self.db) as connection:
                            connection.execute(statement)
        self.assertEqual(current(self.db, "2026-09-16")["close"]["nav"], "10105.00")

    def test_failed_transaction_leaves_previous_version_current(self):
        first, second = self.candidate(), self.candidate()
        self.approve(first)
        publish(self.db, first)
        self.approve(second, 1)
        with self.assertRaisesRegex(RuntimeError, "simulated failure"):
            with database(self.db) as connection:
                connection.execute("INSERT INTO publications VALUES (?, ?, ?, ?)",
                                   ("2026-09-16", 2, second, "test timestamp"))
                raise RuntimeError("simulated failure before commit")
        self.assertEqual(current(self.db, "2026-09-16")["publication"]["version"], 1)
        self.assertIsNone(show(self.db, second)["publication"])
        self.assertEqual(publish(self.db, second), 2)

    def test_candidate_is_frozen_even_if_source_files_change(self):
        candidate = self.candidate()
        source_prices = self.source / "closing_prices.csv"
        source_prices.write_text(source_prices.read_text().replace("18.00", "19.00"))
        self.approve(candidate)
        publish(self.db, candidate)
        self.assertEqual(current(self.db, "2026-09-16")["close"]["nav"], "10105.00")

    def test_overdue_settlement_blocks_approval_even_if_references_agree(self):
        path = self.source / "settlements.csv"
        path.write_text("\n".join(line for line in path.read_text().splitlines() if ",S001," not in line) + "\n")
        cash = self.refs / "broker_cash.csv"
        cash.write_text(cash.read_text().replace("9730.00", "10730.00"))
        nav = land_delivery(self.source, self.root / "landing", "2026-09-14", "nav")
        refs = land_delivery(self.refs, self.root / "landing", "2026-09-16", "references")
        candidate = self.candidate(nav, refs)
        self.assertEqual(show(self.db, candidate)["candidate"]["reconciliation"]["status"], "PASS")
        with self.assertRaisesRegex(ValueError, "overdue settlement"):
            self.approve(candidate)

    def test_cli_prepare_review_approve_publish_and_read(self):
        base = [sys.executable, str(self.repo / "publication.py"), "--database", str(self.db)]
        def run(*args):
            result = subprocess.run(base + list(args), capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()
        candidate = run("prepare", "--business-date", "2026-09-14", "--as-of", "2026-09-16",
                        "--delivery", str(self.nav), "--references", str(self.reference))
        self.assertIsNone(json.loads(run("show", "--candidate", candidate))["approval"])
        run("approve", "--candidate", candidate, "--by", "demo-reviewer", "--note", "Reviewed synthetic example", "--expected-version", "0")
        self.assertIn("1", run("publish", "--candidate", candidate))
        self.assertEqual(json.loads(run("current", "--as-of", "2026-09-16"))["close"]["nav"], "10105.00")
