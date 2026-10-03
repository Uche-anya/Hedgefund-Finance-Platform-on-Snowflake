"""Resolve the saved TEL pair to one cash-dividend event, preserving both inputs."""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from uuid import uuid4

from data_extraction.review_bny_dividends import ROOT, SNAPSHOT
from data_extraction.review_dividend_pairs import TEL
from data_extraction.repair_bny_history import checked_file

IDS = {
    'E0db7c55e9207d0d053fbf9370917fe59c0c4dfee0d5af8de4026cfa31983cb74',
    'E89b4ac9e4c8a74626d9ea08f59bf9b3e20c7fc900cf32ef2dadaf5e321ca942d',
}


def resolve(records):
    if len(records) != 2 or {r['event']['id'] for r in records} != IDS:
        raise ValueError('Expected the two reviewed TEL event IDs')
    events = [r['event'] for r in records]
    comparable = [{k: v for k, v in e.items() if k not in ('id', 'historical_adjustment_factor')} for e in events]
    if comparable[0] != comparable[1]:
        raise ValueError('Payment details differ; review before combining')
    expected = {'ticker': 'TEL', 'record_date': '2024-11-22', 'pay_date': '2024-12-06',
                'declaration_date': '2024-03-13', 'ex_dividend_date': '2024-11-22',
                'currency': 'USD', 'distribution_type': 'recurring', 'frequency': 4}
    if any(events[0].get(k) != v for k, v in expected.items()) or Decimal(str(events[0]['cash_amount'])) != Decimal('0.65'):
        raise ValueError('TEL event no longer matches the reviewed installment')
    return {
        'reviewed_event_id': 'reviewed-TEL-2024-11-22-USD-cash-dividend',
        'event': {**expected, 'cash_amount': '0.65', 'historical_adjustment_factor': None},
        'decision': 'ONE_CASH_ENTITLEMENT',
        'reason': 'Issuer supports one installment; the two provider records agree on cash-payment terms.',
        'evidence_url': TEL,
        'unresolved': 'Provider duplicate cause and conflicting adjustment factors; incorporation change is not a proven cause.',
        'ex_date_evidence': 'Both provider records agree; issuer notice independently confirms record and payment dates and amount.',
        'scope': 'Cash-dividend consolidation only. Eligibility, security mapping and cash receipt remain separate checks.',
        'source_records': records,
    }


def main():
    manifest = json.loads((SNAPSHOT / 'manifest.json').read_text())
    payload = checked_file(SNAPSHOT / 'dividends.jsonl', manifest['dividends']['sha256'])
    records = [json.loads(line) for line in payload.decode().splitlines()]
    selected = [r for r in records if r['event']['ticker'] == 'TEL' and r['event']['ex_dividend_date'] == '2024-11-22']
    resolved = resolve(selected)
    folder = ROOT / 'data/corporate_action_reviews' / uuid4().hex
    folder.mkdir(parents=True)
    output = folder / 'tel_reviewed_event.json'
    output.write_text(json.dumps(resolved, indent=2) + '\n', encoding='utf-8')
    summary = {'reviewed_at': datetime.now(timezone.utc).isoformat(), 'snapshot': SNAPSHOT.name,
        'input_sha256': hashlib.sha256(payload).hexdigest(), 'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'source_event_ids': sorted(IDS), 'reviewed_event_id': resolved['reviewed_event_id'],
        'supersedes': '26e32fc523e24ab08a0c479c0369e423: TEL HOLD_FOR_REVIEW for cash-entitlement duplication only',
        'applied_to_snowflake': False}
    (folder / 'manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'Two source records -> one reviewed USD 0.65 dividend. Saved: {output}')


if __name__ == '__main__':
    main()
