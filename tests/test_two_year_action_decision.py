from decimal import Decimal
import unittest

from scripts.preview_two_year_action_decision import check_decision, preview_rows


class DecisionPreviewTests(unittest.TestCase):
    def test_hold_keeps_nav_and_shows_approval_effect(self):
        event = {'event_id': 'd1', 'security_id': 's1',
                 'ex_dividend_date': '2026-05-19', 'pay_date': '2026-06-10',
                 'cash_per_share_usd': '2', 'review_status': 'PENDING'}
        entitlements = [
            {'event_id': 'd1', 'account_id': account, 'security_id': 's1',
             'ex_dividend_date': '2026-05-19', 'pay_date': '2026-06-10',
             'cash_per_share_usd': '2', 'opening_quantity': shares,
             'gross_amount_usd': amount, 'review_status': 'PENDING',
             'payment_status': 'NO_CONFIRMATION'}
            for account, shares, amount in (('SIM-REPLAY-01', '-5', '-10'),
                                            ('SIM-REPLAY-02', '4', '8'))
        ]
        daily = [
            {'business_date': day, 'account_id': account,
             'nav_excluding_pending_actions_usd': '100',
             'pending_candidate_impact_usd': pending,
             'illustrative_nav_usd': illustrative}
            for day, pending, illustrative in (('2026-05-18', '0', '100'),
                                               ('2026-05-19', '5', '105'))
            for account in ('SIM-REPLAY-01', 'SIM-REPLAY-02')
        ]
        decision = {'decision': 'HOLD'}

        rows, amounts = preview_rows(daily, event, entitlements, decision)

        self.assertEqual(len(rows), 2)
        self.assertEqual(amounts['SIM-REPLAY-01'], Decimal('-10'))
        self.assertEqual(rows[0]['decision_nav_usd'], '100')
        self.assertEqual(rows[0]['nav_if_approved_usd'], '90')
        self.assertEqual(rows[0]['pending_impact_if_approved_usd'], '15')
        self.assertEqual(rows[1]['nav_if_approved_usd'], '108')
        self.assertEqual(rows[1]['pending_impact_if_approved_usd'], '-3')

        approved_rows, _ = preview_rows(daily, event, entitlements,
                                        {'decision': 'APPROVE'})
        self.assertEqual(approved_rows[0]['decision_nav_usd'], '90')
        self.assertEqual(approved_rows[1]['decision_nav_usd'], '108')

    def test_approval_requires_evidence(self):
        event = {'event_id': 'd1', 'review_status': 'PENDING'}
        decision = {'schema_version': 1, 'decision_id': 'test_approval',
                    'event_id': 'd1', 'decision': 'APPROVE',
                    'reason': 'Checked', 'recorded_by': 'reviewer'}
        with self.assertRaisesRegex(ValueError, 'Approval needs'):
            check_decision(decision, event)


if __name__ == '__main__':
    unittest.main()
