import json
import os
import subprocess
import sys
import unittest

from pipeline.environment import get_environment


class EnvironmentTests(unittest.TestCase):
    def test_unknown_environment_stops(self):
        with self.assertRaisesRegex(ValueError, "Unknown Northbridge environment"):
            get_environment("uat")

    def test_pipeline_names_follow_selected_environment(self):
        script = (
            "import json; "
            "from pipeline import load_day, prices, daily_simulator; "
            "print(json.dumps([load_day.STAGE, prices.TABLE, daily_simulator.NAV]))"
        )
        for target in ("test", "prod"):
            env = os.environ.copy()
            env["NORTHBRIDGE_ENV"] = target
            output = subprocess.check_output([sys.executable, "-c", script], env=env,
                                             text=True)
            names = json.loads(output)
            database = "NORTHBRIDGE_" + target.upper()
            self.assertEqual(names, [
                database + ".RAW.DAILY_LANDING",
                database + ".RAW.DAILY_PRICE_EVENTS",
                database + ".DBT_" + target.upper() + ".FCT_NAV_DAILY",
            ])


if __name__ == "__main__":
    unittest.main()
