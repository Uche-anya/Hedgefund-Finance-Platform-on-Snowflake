"""Record BNY ticker-reuse exclusions separately from downloaded dividends."""

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from data_extraction.repair_bny_history import check_references, REFERENCES, CHANGE_DATE, BANK_FIGI, checked_file
from data_extraction.corporate_actions import ROOT

SNAPSHOT = ROOT / 'data/corporate_actions/7962b1659329451b86a5eb288fd7d61e'
BANK_NOTICE = 'https://www.bny.com/corporate/global/en/about-us/newsroom/press-release/bny-announces-planned-change-of-stock-ticker-symbol-to-bny-130465.html'
FUND_NOTICE = 'https://www.blackrock.com/us/individual/literature/press-release/1-2-26-pr-muni-div-release.pdf'


def classify(event):
    ticker, day = event['ticker'], event['ex_dividend_date']
    if ticker == 'BNY' and day < CHANGE_DATE:
        return 'EXCLUDED_FROM_BANK', 'BNY predates bank ticker change; belongs outside the reviewed bank ticker history'
    return 'NEEDS_REVIEW', 'Fits bank ticker period only; dividend entitlement and event identity still need review'


def main():
    evidence = check_references(REFERENCES)
    manifest = json.loads((SNAPSHOT / 'manifest.json').read_text())
    payload = checked_file(SNAPSHOT / 'dividends.jsonl', manifest['dividends']['sha256'])
    records = [json.loads(line) for line in payload.decode().splitlines()]
    decisions = []
    for record in records:
        event = record['event']
        if event['ticker'] not in ('BNY', 'BK'):
            continue
        status, reason = classify(event)
        decisions.append({'event_id': event['id'], 'ticker': event['ticker'],
            'ex_dividend_date': event['ex_dividend_date'], 'cash_amount': event['cash_amount'],
            'currency': event['currency'], 'decision': status, 'reason': reason,
            'target_instrument': 'US_BNY_MELLON_COMMON', 'target_share_class_figi': BANK_FIGI,
            'source_file': record['source_file'], 'source_row_number': record['source_row_number']})
    excluded = [r for r in decisions if r['decision'] == 'EXCLUDED_FROM_BANK']
    if len(excluded) != 17:
        raise ValueError('Expected the 17 reviewed BNY candidates; inspect changed input before proceeding')
    folder = ROOT / 'data/corporate_action_reviews' / uuid4().hex
    folder.mkdir(parents=True)
    output = folder / 'bny_decisions.csv'
    with output.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(decisions[0]))
        writer.writeheader()
        writer.writerows(decisions)
    summary = {'reviewed_at': datetime.now(timezone.utc).isoformat(),
        'corporate_action_snapshot': SNAPSHOT.name,
        'dividends_sha256': hashlib.sha256(payload).hexdigest(),
        'reference_files': {name: hashlib.sha256(raw).hexdigest() for name, raw in evidence.items()},
        'decision_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'sources': [BANK_NOTICE, FUND_NOTICE], 'bank_ticker_change': CHANGE_DATE,
        'excluded_from_bank': len(excluded), 'bank_period_candidates_needing_review': len(decisions) - len(excluded),
        'excluded_date_range': [min(r['ex_dividend_date'] for r in excluded), max(r['ex_dividend_date'] for r in excluded)],
        'scope': 'Exclusion from bank calculations only; not event-by-event certification of BlackRock distributions. No other event is approved.',
        'applied_to_snowflake': False}
    (folder / 'manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    print(f'Decisions: {output}')


if __name__ == '__main__':
    main()
