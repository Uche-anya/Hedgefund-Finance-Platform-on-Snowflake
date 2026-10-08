import copy
import shutil
import tempfile
from pathlib import Path
import unittest

from scripts.close_daily_pilot import check_settlements
from simulation.daily_settlements import generate, read_trades


class SettlementPilotTests(unittest.TestCase):
    def test_saved_confirmations_match_due_trades(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenario = 'sim-equity-2024-2026-v1'
            source = Path('data/daily_oms') / scenario
            pilot_days = ['2024-09-24', '2024-09-25', '2024-09-26',
                          '2024-09-27', '2024-09-30']
            for day in pilot_days:
                target = root / 'oms' / scenario / day
                target.mkdir(parents=True)
                for name in ('oms.jsonl', 'manifest.json'):
                    shutil.copy2(source / day / name, target / name)
            output = root / 'settlements'
            days = generate(oms_root=root / 'oms', output=output)
            self.assertEqual(days, ['2024-09-25', '2024-09-26', '2024-09-27',
                                    '2024-09-30', '2024-10-01'])
            trades = read_trades(root / 'oms' / scenario)
            prior = {trade['execution_id']: trade for trade in trades}
            from scripts.close_daily_pilot import saved_delivery
            for day in days:
                _, confirmations = saved_delivery(
                    output / 'sim-equity-2024-2026-v1' / day, 'settlements.jsonl')
                check_settlements(day, confirmations, prior)
            self.assertEqual(len(trades), 20)

    def test_missing_or_wrong_cash_confirmation_stops_close(self):
        trade = {'execution_id': 'e1', 'settlement_due': '2024-09-25',
                 'account_id': 'A', 'instrument_id': 'AAPL.US', 'side': 'BUY',
                 'quantity': '2', 'execution_price': '100.00'}
        confirmation = {'execution_id': 'e1', 'account_id': 'A',
                        'instrument_id': 'AAPL.US', 'side': 'BUY',
                        'settled_quantity': '2', 'cash_amount': '-200.00'}
        check_settlements('2024-09-25', [confirmation], {'e1': trade})
        with self.assertRaisesRegex(ValueError, 'differ from trades due'):
            check_settlements('2024-09-25', [], {'e1': trade})
        wrong = copy.deepcopy(confirmation)
        wrong['cash_amount'] = '-199.00'
        with self.assertRaisesRegex(ValueError, 'differs from e1'):
            check_settlements('2024-09-25', [wrong], {'e1': trade})


if __name__ == '__main__':
    unittest.main()
