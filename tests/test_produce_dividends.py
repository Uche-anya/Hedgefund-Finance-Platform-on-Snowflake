"""Dry runs stay local, and submissions use the prepared snapshot."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.produce_dividends import run


class ProduceDividendsTest(unittest.TestCase):
    @patch("pipeline.produce_dividends.snowflake_connection")
    @patch("pipeline.produce_dividends.dividends.prepare")
    @patch("pipeline.produce_dividends.massive_dividends.fetch")
    def test_dry_run_stops_before_snowflake(self, fetch, prepare, connect):
        folder = Path("data/example")
        fetch.return_value = folder
        prepare.return_value = {"rows": 2}
        self.assertEqual(run("2026-10-13", Path("data"), False), folder)
        connect.assert_not_called()

    @patch("pipeline.produce_dividends.snowflake_connection")
    @patch("pipeline.produce_dividends.dividends.submit")
    @patch("pipeline.produce_dividends.dividends.prepare")
    @patch("pipeline.produce_dividends.massive_dividends.fetch")
    def test_submit_uses_prepared_snapshot(self, fetch, prepare, submit, connect):
        fetch.return_value = Path("data/example")
        item = {"rows": 2, "id": "delivery-1"}
        prepare.return_value = item
        context = MagicMock()
        connect.return_value.__enter__.return_value = context
        run("2026-10-13", Path("data"), True)
        submit.assert_called_once_with(context.cursor.return_value.__enter__.return_value,
                                       item)

    @patch("pipeline.produce_dividends.massive_dividends.fetch")
    def test_weekend_has_no_fetch(self, fetch):
        with self.assertRaises(ValueError):
            run("2026-10-11", Path("data"), True)
        fetch.assert_not_called()

    @patch("pipeline.produce_dividends.snowflake_connection")
    @patch("pipeline.produce_dividends.dividends.prepare", return_value={"rows": 0})
    @patch("pipeline.produce_dividends.massive_dividends.fetch")
    def test_empty_market_snapshot_is_not_submitted(self, fetch, prepare, connect):
        with self.assertRaisesRegex(RuntimeError, "no dividends"):
            run("2026-10-13", Path("data"), True)
        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
