from datetime import datetime
from decimal import Decimal
import unittest

from simulation.bank_statement import expected_balances


class BankStatementTests(unittest.TestCase):
    def test_cash_sources_are_applied_once(self):
        replay = [
            {'record_type': 'OPENING_CASH', 'account_id': 'A', 'amount': '100'},
            {'record_type': 'SETTLEMENT', 'account_id': 'A', 'cash_amount': '-20',
             'settled_at': '2025-01-02T10:00:00+00:00', 'published_at': '2025-01-02T10:01:00+00:00'},
        ]
        admin = [
            {'event_type': 'INVESTOR_SUBSCRIPTION', 'account_id': 'A',
             'event_date': '2025-01-02', 'amount': '30'},
            {'event_type': 'EXPENSE', 'account_id': 'A', 'event_date': '2025-01-02',
             'payment_date': '2025-01-03', 'amount': '5'},
        ]
        balances = expected_balances(replay, admin, datetime.fromisoformat('2025-01-03T22:00:00+00:00'))
        self.assertEqual(balances['A'], Decimal('105'))
