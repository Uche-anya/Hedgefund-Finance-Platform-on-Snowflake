import csv
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fund_pipeline.action_restatement import reclassify_close
from scripts.apply_two_year_action_decision import run
from scripts.preview_two_year_action_decision import check_decision, csv_bytes, preview_rows


class ActionRestatementTests(unittest.TestCase):
    def test_fictional_approval_moves_accrual_without_changing_cash_or_illustrative_nav(self):
        event = {'event_id': 'fixture-dividend', 'security_id': 'fixture-security',
                 'ex_dividend_date': '2026-05-19', 'pay_date': '2026-06-10',
                 'cash_per_share_usd': '2', 'review_status': 'PENDING'}
        decision = {
            'schema_version': 1, 'decision_id': 'fixture_approval_01',
            'event_id': event['event_id'], 'decision': 'APPROVE',
            'reason': 'Fictional issuer, identity and account records agree.',
            'recorded_by': 'test fixture', 'reviewer': 'Fictional Reviewer',
            'evidence': {
                'issuer_notice': 'fixture:issuer',
                'ex_date_source': 'fixture:ex-date',
                'security_identity': 'fixture:identity',
                'account_eligibility': 'fixture:account',
            },
        }
        check_decision(decision, event)
        amounts = {'SIM-REPLAY-01': Decimal('-10'), 'SIM-REPLAY-02': Decimal('8')}
        daily = []
        for day in ('2026-05-18', '2026-05-19', '2026-05-20'):
            for account, amount in amounts.items():
                active = day >= event['ex_dividend_date']
                short = max(-amount, Decimal(0)) if active else Decimal(0)
                long = max(amount, Decimal(0)) if active else Decimal(0)
                daily.append({
                    'business_date': day, 'account_id': account,
                    'settled_cash_usd': '100',
                    'dividend_receivable_unconfirmed_usd': str(long),
                    'short_dividend_payable_unconfirmed_usd': str(short),
                    'reviewed_dividend_receivable_usd': '0',
                    'reviewed_short_dividend_payable_usd': '0',
                    'pending_dividend_receivable_usd': str(long),
                    'pending_short_dividend_payable_usd': str(short),
                    'pending_candidate_impact_usd': str(long - short),
                    'pending_review_dividend_net_usd': str(long - short),
                    'nav_excluding_pending_actions_usd': '100',
                    'illustrative_nav_usd': str(100 + long - short),
                })
        entitlements = [{
            'event_id': event['event_id'], 'account_id': account,
            'gross_amount_usd': str(amount), 'review_status': 'PENDING',
            'payment_status': 'NO_CONFIRMATION',
        } for account, amount in amounts.items()]

        updated, approved, differences = reclassify_close(
            daily, entitlements, event, amounts)

        self.assertEqual(updated[0], daily[0])
        self.assertEqual(updated[1], daily[1])
        self.assertEqual(len(differences), 4)
        self.assertEqual(updated[2]['nav_excluding_pending_actions_usd'], '90')
        self.assertEqual(updated[3]['nav_excluding_pending_actions_usd'], '108')
        self.assertEqual(updated[2]['pending_short_dividend_payable_usd'], '0')
        self.assertEqual(updated[2]['reviewed_short_dividend_payable_usd'], '10')
        self.assertEqual(updated[3]['pending_dividend_receivable_usd'], '0')
        self.assertEqual(updated[3]['reviewed_dividend_receivable_usd'], '8')
        for before, after in zip(daily, updated):
            self.assertEqual(after['settled_cash_usd'], before['settled_cash_usd'])
            self.assertEqual(after['illustrative_nav_usd'], before['illustrative_nav_usd'])
        self.assertEqual({row['review_status'] for row in approved},
                         {'APPROVED_BY_DECISION'})
        self.assertEqual({row['review_status'] for row in entitlements}, {'PENDING'})

    def test_hold_writes_no_new_close(self):
        reviewed = ({'decision': 'HOLD'}, {}, [], [], [], {}, {}, {})
        with patch('scripts.apply_two_year_action_decision.load_review', return_value=reviewed):
            self.assertIsNone(run(Path('fixture.json')))

    def test_approval_writes_a_versioned_fixture_close(self):
        event = {'event_id': 'fixture-dividend', 'security_id': 'fixture-security',
                 'ex_dividend_date': '2026-05-19', 'pay_date': '2026-06-10',
                 'cash_per_share_usd': '2', 'review_status': 'PENDING'}
        amounts = {'SIM-REPLAY-01': Decimal('-10'), 'SIM-REPLAY-02': Decimal('8')}
        daily = []
        for day in ('2026-05-18', '2026-05-19'):
            for account, amount in amounts.items():
                active = day >= event['ex_dividend_date']
                receipt = max(amount, Decimal(0)) if active else Decimal(0)
                payable = max(-amount, Decimal(0)) if active else Decimal(0)
                daily.append({
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
        entitlements = [{
            'event_id': event['event_id'], 'account_id': account,
            'gross_amount_usd': str(amount), 'review_status': 'PENDING',
            'payment_status': 'NO_CONFIRMATION',
        } for account, amount in amounts.items()]
        decision = {'decision_id': 'fixture_approval_01', 'decision': 'APPROVE'}
        preview, _ = preview_rows(daily, event, [
            dict(row, security_id=event['security_id'],
                 ex_dividend_date=event['ex_dividend_date'],
                 pay_date=event['pay_date'],
                 cash_per_share_usd=event['cash_per_share_usd'],
                 opening_quantity=str(amounts[row['account_id']] / 2))
            for row in entitlements
        ], decision)
        queue_manifest = {'scenario_id': 'fictional-test', 'queue_sha256': 'fixture-queue'}
        close_manifest = {
            'review_split': {'pending_event_ids': 1, 'reviewed_event_ids': 0},
            'files': {'positions.csv': {'sha256': 'fixture-position'},
                      'security_transfers.csv': {'sha256': 'fixture-transfer'}},
        }
        reviewed = (decision, event, daily, entitlements, preview, amounts,
                    queue_manifest, close_manifest)

        with TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / 'source'
            source.mkdir()
            (source / 'dividend_entitlements.csv').write_bytes(csv_bytes(entitlements))
            (source / 'manifest.json').write_text(json.dumps(close_manifest), encoding='utf-8')
            decision_path = folder / 'decision.json'
            decision_path.write_text(json.dumps(decision), encoding='utf-8')
            target = folder / 'versions'
            with (patch('scripts.apply_two_year_action_decision.load_review', return_value=reviewed),
                  patch('scripts.apply_two_year_action_decision.CLOSE', source),
                  patch('scripts.apply_two_year_action_decision.OUTPUT', target)):
                result = run(decision_path)
                self.assertEqual(run(decision_path), result)
            saved = target / decision['decision_id']
            with (saved / 'daily.csv').open(newline='', encoding='utf-8') as handle:
                new_daily = list(csv.DictReader(handle))
            self.assertEqual(result['status'], 'PROVISIONAL_UNAPPROVED')
            self.assertEqual(result['affected_account_day_rows'], 2)
            self.assertEqual(result['pending_event_ids'], 0)
            self.assertEqual(new_daily[0], daily[0])
            self.assertEqual(new_daily[2]['nav_excluding_pending_actions_usd'], '90')
            self.assertEqual(new_daily[3]['nav_excluding_pending_actions_usd'], '108')
            self.assertEqual(new_daily[2]['illustrative_nav_usd'], daily[2]['illustrative_nav_usd'])


if __name__ == '__main__':
    unittest.main()
