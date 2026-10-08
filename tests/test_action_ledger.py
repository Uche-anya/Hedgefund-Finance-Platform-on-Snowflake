from decimal import Decimal
import json
from pathlib import Path
import unittest

from fund_pipeline.action_restatement import apply_ledger


class ActionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.accounts = ('SIM-REPLAY-01', 'SIM-REPLAY-02')
        self.actions = [
            ('first', '2026-05-19', {'SIM-REPLAY-01': '-10',
                                     'SIM-REPLAY-02': '8'}, 'APPROVE'),
            ('second', '2026-05-20', {'SIM-REPLAY-01': '4',
                                      'SIM-REPLAY-02': '-6'}, 'APPROVE'),
            ('held', '2026-05-20', {'SIM-REPLAY-01': '3',
                                    'SIM-REPLAY-02': '2'}, 'HOLD'),
        ]
        self.entries = []
        self.entitlements = []
        for event_id, ex_date, amounts, status in self.actions:
            self.entries.append((
                {'decision_id': event_id + '_decision', 'event_id': event_id,
                 'decision': status},
                {'event_id': event_id, 'ex_dividend_date': ex_date},
                {account: Decimal(value) for account, value in amounts.items()},
            ))
            for account, amount in amounts.items():
                self.entitlements.append({
                    'event_id': event_id, 'account_id': account,
                    'gross_amount_usd': amount, 'review_status': 'PENDING',
                    'payment_status': 'NO_CONFIRMATION',
                })
        cvx_path = (Path(__file__).resolve().parents[1]
                    / 'docs/action_reviews/cvx_2026-05-19.json')
        cvx_hold = json.loads(cvx_path.read_text(encoding='utf-8'))
        self.entries.append((cvx_hold, {'event_id': cvx_hold['event_id']}, {}))
        self.cvx_event_id = cvx_hold['event_id']
        self.daily = []
        for day in ('2026-05-18', '2026-05-19', '2026-05-20'):
            for account in self.accounts:
                active = [Decimal(amounts[account])
                          for _, ex_date, amounts, _ in self.actions if day >= ex_date]
                receipt = sum((max(value, 0) for value in active), Decimal(0))
                payable = sum((max(-value, 0) for value in active), Decimal(0))
                self.daily.append({
                    'business_date': day, 'account_id': account,
                    'settled_cash_usd': '100',
                    'dividend_receivable_unconfirmed_usd': str(receipt),
                    'short_dividend_payable_unconfirmed_usd': str(payable),
                    'reviewed_dividend_receivable_usd': '0',
                    'reviewed_short_dividend_payable_usd': '0',
                    'pending_dividend_receivable_usd': str(receipt),
                    'pending_short_dividend_payable_usd': str(payable),
                    'pending_candidate_impact_usd': str(receipt - payable),
                    'pending_review_dividend_net_usd': str(receipt - payable),
                    'nav_excluding_pending_actions_usd': '100',
                    'illustrative_nav_usd': str(100 + receipt - payable),
                })

    def test_two_approvals_add_up_and_hold_stays_pending(self):
        daily, entitlements, report, approved, held = apply_ledger(
            self.daily, self.entitlements, self.entries)

        self.assertEqual(approved, ['first', 'second'])
        self.assertEqual(held, [self.cvx_event_id, 'held'])
        self.assertEqual(len(report), 4)
        self.assertEqual(daily[2]['nav_excluding_pending_actions_usd'], '90')
        self.assertEqual(daily[3]['nav_excluding_pending_actions_usd'], '108')
        self.assertEqual(daily[4]['nav_excluding_pending_actions_usd'], '94')
        self.assertEqual(daily[5]['nav_excluding_pending_actions_usd'], '102')
        self.assertEqual(daily[4]['pending_candidate_impact_usd'], '3')
        self.assertEqual(daily[5]['pending_candidate_impact_usd'], '2')
        self.assertEqual(report[-1]['approved_event_ids'], 'first|second')
        self.assertEqual([row['review_status'] for row in entitlements],
                         ['APPROVED_BY_DECISION'] * 4 + ['PENDING'] * 2)
        for before, after in zip(self.daily, daily):
            self.assertEqual(before['illustrative_nav_usd'], after['illustrative_nav_usd'])
            self.assertEqual(before['settled_cash_usd'], after['settled_cash_usd'])
        backwards = apply_ledger(self.daily, self.entitlements, list(reversed(self.entries)))
        self.assertEqual(backwards, (daily, entitlements, report, approved, held))

    def test_same_event_cannot_be_decided_twice(self):
        with self.assertRaisesRegex(ValueError, 'Repeated or conflicting'):
            apply_ledger(self.daily, self.entitlements,
                         self.entries + [self.entries[0]])
        repeated_id = (dict(self.entries[1][0],
                            decision_id=self.entries[0][0]['decision_id']),
                       self.entries[1][1], self.entries[1][2])
        with self.assertRaisesRegex(ValueError, 'Repeated or conflicting'):
            apply_ledger(self.daily, self.entitlements,
                         [self.entries[0], repeated_id])


if __name__ == '__main__':
    unittest.main()
