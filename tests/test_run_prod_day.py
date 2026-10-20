import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts import run_prod_day


class RunProdDayTests(unittest.TestCase):
    def test_requires_prod_environment(self):
        with patch.object(run_prod_day, "get_environment", return_value=SimpleNamespace(name="dev")):
            with self.assertRaisesRegex(ValueError, "NORTHBRIDGE_ENV=prod"):
                run_prod_day.run("2026-10-19", "scenario", "2026-10-15", Path("data"))

    def test_closed_market_date_does_not_connect(self):
        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_INGEST_PROD"}):
            with patch.object(run_prod_day, "get_environment", return_value=SimpleNamespace(name="prod")):
                with patch.object(run_prod_day, "is_market_day", return_value=False):
                    with patch.object(run_prod_day, "snowflake_connection") as connect:
                        run_prod_day.run("2026-10-17", "scenario", "2026-10-15", Path("data"))
                        connect.assert_not_called()

    def test_validated_date_does_not_redeliver(self):
        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_INGEST_PROD"}):
            with patch.object(run_prod_day, "get_environment", return_value=SimpleNamespace(name="prod")):
                with patch.object(run_prod_day, "snowflake_connection", return_value=MagicMock()):
                    with patch.object(run_prod_day.produce_day, "close_is_validated", return_value=True):
                        with patch.object(run_prod_day.produce_day, "run") as market:
                            run_prod_day.run("2026-10-19", "scenario", "2026-10-15", Path("data"))
                            market.assert_not_called()

    def test_waits_for_events_before_bank(self):
        with patch.dict(os.environ, {"SNOWFLAKE_ROLE": "NORTHBRIDGE_INGEST_PROD"}):
            with patch.object(run_prod_day, "get_environment", return_value=SimpleNamespace(name="prod")):
                with patch.object(run_prod_day, "snowflake_connection", return_value=MagicMock()):
                    with patch.object(run_prod_day.produce_day, "close_is_validated", return_value=False):
                        with patch.object(run_prod_day.produce_day, "run") as market:
                            with patch.object(run_prod_day.produce_dividends, "run") as dividends:
                                with patch.object(run_prod_day, "check_source", return_value=(True, "ready")) as source:
                                    with patch.object(run_prod_day.produce_bank, "run") as bank:
                                        with patch.object(run_prod_day, "readiness", return_value=[(True, "ready")]):
                                            run_prod_day.run("2026-10-19", "scenario", "2026-10-15", Path("data"))
        market.assert_called_once()
        dividends.assert_called_once()
        self.assertEqual(source.call_count, 2)
        bank.assert_called_once()


if __name__ == "__main__":
    unittest.main()
