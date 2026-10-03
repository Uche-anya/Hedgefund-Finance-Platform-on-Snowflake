from pathlib import Path
import tempfile
import unittest

from simulation.fund_administrator import produce


class FundAdministratorTests(unittest.TestCase):
    def test_saved_delivery_is_reusable(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            first = produce(output=output)
            second = produce(output=output)
            self.assertEqual(first, second)
            self.assertEqual(len((first / 'events.jsonl').read_text().splitlines()), 4)
