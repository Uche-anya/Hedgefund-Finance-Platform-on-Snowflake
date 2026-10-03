from decimal import Decimal
import unittest

from simulation.broker_statement import apply_exceptions, closing_positions


class BrokerStatementTests(unittest.TestCase):
    def test_positions_are_calculated_without_dbt_output(self):
        records = [
            {'record_type': 'EXECUTION', 'business_date': '2025-01-06',
             'account_id': 'A1', 'market_ticker': 'AAPL', 'side': 'BUY', 'quantity': '10'},
            {'record_type': 'EXECUTION', 'business_date': '2025-01-07',
             'account_id': 'A1', 'market_ticker': 'AAPL', 'side': 'SELL', 'quantity': '3'},
            {'record_type': 'SETTLEMENT', 'business_date': '2025-01-07',
             'account_id': 'A1', 'market_ticker': 'AAPL', 'side': 'SELL', 'quantity': '3'},
        ]
        self.assertEqual(closing_positions(records, '2025-01-07'),
                         {('A1', 'AAPL'): Decimal('7')})

    def test_configured_exceptions_change_only_the_broker_copy(self):
        original = {('A1', 'AAPL'): Decimal('10'), ('A1', 'MSFT'): Decimal('4')}
        config = {
            'quantity_adjustments': [
                {'account_id': 'A1', 'ticker': 'AAPL', 'change': '2', 'label': 'WRONG_QUANTITY'}],
            'omitted_positions': [
                {'account_id': 'A1', 'ticker': 'MSFT', 'label': 'MISSING_FROM_BROKER'}],
            'extra_positions': [
                {'account_id': 'A2', 'ticker': 'AAPL', 'quantity': '5',
                 'label': 'UNEXPECTED_ACCOUNT_POSITION'}],
        }
        changed, labels = apply_exceptions(original, config)
        self.assertEqual(original[('A1', 'AAPL')], Decimal('10'))
        self.assertEqual(changed, {('A1', 'AAPL'): Decimal('12'),
                                   ('A2', 'AAPL'): Decimal('5')})
        self.assertEqual(len(labels), 3)


if __name__ == '__main__':
    unittest.main()
