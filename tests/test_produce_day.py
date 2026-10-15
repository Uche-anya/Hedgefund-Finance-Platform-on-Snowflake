"""A completed close should not trigger another market request."""

import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.produce_day import run


class ProducerRetryTest(unittest.TestCase):
    @patch("pipeline.produce_day.load_day.snowflake_connection")
    @patch("pipeline.produce_day.massive_prices.fetch")
    def test_validated_close_skips_fetch(self, fetch, connect):
        cursor = connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        run("2026-10-13", "sim-close-20261008", Path("data"), True)
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
