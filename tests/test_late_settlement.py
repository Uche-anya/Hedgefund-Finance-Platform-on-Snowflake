from datetime import datetime
import unittest

from simulation.late_settlement import late_confirmation


class LateSettlementTests(unittest.TestCase):
    def test_late_publication_preserves_original_settlement_and_trade(self):
        trade = dict(market_ticker='AMZN', side='BUY', quantity='2',
                     execution_price='224.26', execution_id='SIM-EXEC-example',
                     fund_id='NORTHBRIDGE', account_id='SIM-ACCOUNT-01',
                     broker_id='SIM-BROKER-01', instrument_id='AMZN.US', currency='USD')
        event = late_confirmation([trade])
        cutoff = datetime.fromisoformat('2025-01-07T22:00:00+00:00')
        self.assertLess(datetime.fromisoformat(event['settled_at']), cutoff)
        self.assertGreater(datetime.fromisoformat(event['published_at']), cutoff)
        self.assertEqual(event['cash_amount'], '-448.52')
        self.assertEqual(event['execution_id'], trade['execution_id'])
        self.assertEqual(event, late_confirmation([trade]))
        self.assertTrue(event['is_simulated'])

    def test_ambiguous_or_missing_trade_rejected(self):
        with self.assertRaises(ValueError):
            late_confirmation([])
        with self.assertRaises(ValueError):
            late_confirmation([dict(market_ticker='AMZN', side='BUY')] * 2)
