import json
import tempfile
import unittest
from pathlib import Path

from pipeline.check_day import check_oms_reports
from pipeline.incident_drill import make_conflict
from pipeline.load_day import delivery


class IncidentDrillTest(unittest.TestCase):
    def test_conflicting_retransmission_is_stopped_before_snowpipe(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = make_conflict(root, "2026-10-09", "sim-oms-conflict-drill")
            reports = [json.loads(line) for line in
                       (folder / "oms.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["quantity"] for row in reports], ["10", "12"])
            self.assertEqual(reports[0]["execution_id"], reports[1]["execution_id"])

            with self.assertRaisesRegex(ValueError, "Conflicting OMS report"):
                delivery(root, "sim-oms-conflict-drill", "2026-10-09", "oms")

            repeated = dict(reports[1], quantity="10")
            check_oms_reports([reports[0], repeated])

            corrected = dict(reports[1], execution_version=2)
            check_oms_reports([reports[0], corrected])


if __name__ == "__main__":
    unittest.main()
