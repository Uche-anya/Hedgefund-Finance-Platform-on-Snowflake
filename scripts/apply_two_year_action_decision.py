"""Write a versioned provisional close for one approved dividend decision."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fund_pipeline.action_restatement import reclassify_close
from scripts.preview_two_year_action_decision import (
    CLOSE, csv_bytes, load_review, read_csv, sha256,
)
from simulation.daily_oms import write_once

OUTPUT = ROOT / 'data/two_year_close/review_decisions'


def run(decision_path):
    (decision, event, daily, selected_entitlements, preview, amounts,
     queue_manifest, close_manifest) = load_review(decision_path)
    if decision['decision'] == 'HOLD':
        print('HOLD: no close written; reviewed NAV stays as saved.')
        return None

    all_entitlements = read_csv(CLOSE / 'dividend_entitlements.csv')
    new_daily, new_entitlements, differences = reclassify_close(
        daily, all_entitlements, event, amounts)
    if len(differences) != len(preview):
        raise ValueError('Restatement and preview cover different rows')
    for changed, expected in zip(differences, preview):
        if (changed['business_date'] != expected['business_date']
                or changed['account_id'] != expected['account_id']
                or changed['reviewed_nav_after_usd'] != expected['decision_nav_usd']):
            raise ValueError('Restatement differs from the decision preview')

    folder = OUTPUT / decision['decision_id']
    files = {}
    for name, rows in (('daily.csv', new_daily),
                       ('dividend_entitlements.csv', new_entitlements),
                       ('nav_differences.csv', differences)):
        body = csv_bytes(rows)
        write_once(folder / name, body)
        files[name] = {'rows': len(rows), 'sha256': hashlib.sha256(body).hexdigest()}
    result = {
        'scenario_id': queue_manifest['scenario_id'],
        'status': 'PROVISIONAL_UNAPPROVED',
        'decision_id': decision['decision_id'],
        'event_id': event['event_id'],
        'decision': 'APPROVE',
        'source_close_manifest_sha256': sha256(CLOSE / 'manifest.json'),
        'source_queue_sha256': queue_manifest['queue_sha256'],
        'decision_sha256': sha256(decision_path),
        'affected_market_days': len({row['business_date'] for row in differences}),
        'affected_account_day_rows': len(differences),
        'pending_event_ids': close_manifest['review_split']['pending_event_ids'] - 1,
        'reviewed_event_ids': close_manifest['review_split']['reviewed_event_ids'] + 1,
        'unchanged_source_files': {
            name: close_manifest['files'][name]['sha256']
            for name in ('positions.csv', 'security_transfers.csv')
        },
        'files': files,
        'limitations': ('This is a review reclassification of an existing accrual, '
                        'not a new trade, market-price or payment calculation. '
                        'Other pending actions and cash evidence gaps remain.'),
    }
    write_once(folder / 'manifest.json',
               (json.dumps(result, indent=2, sort_keys=True) + '\n').encode())
    print(f"APPROVE: wrote {len(new_daily)} provisional close rows and "
          f"{len(differences)} reviewed-NAV differences")
    print(folder)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--decision', type=Path, required=True)
    args = parser.parse_args()
    run(args.decision.resolve())
