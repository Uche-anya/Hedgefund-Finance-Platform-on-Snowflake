"""Record evidence-based decisions for the ten reviewed dividend pairs."""

from collections import defaultdict, Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from uuid import uuid4

from data_extraction.review_bny_dividends import SNAPSHOT, ROOT
from data_extraction.repair_bny_history import checked_file

FCX = 'https://investors.fcx.com/investors/stock-and-dividend-information/dividend-history/default.aspx'
FORD = 'https://s205.q4cdn.com/882619693/files/doc_financials/2025/q2/Ford-Q2-2025-10-Q-Report.pdf'
FORD_DATES = 'https://www.miaxglobal.com/sites/default/files/alert-files/F_Distribution__56018.pdf'
TEL = 'https://investors.te.com/news-releases/press-release-details/2024/TE-Connectivity-completes-change-in-place-of-incorporation-to-Ireland/default.aspx'
FCX_DATES = {'2024-10-15': '2024-11-01', '2025-01-15': '2025-02-03',
    '2025-04-15': '2025-05-01', '2025-07-15': '2025-08-01',
    '2025-10-15': '2025-11-03', '2026-01-15': '2026-02-02',
    '2026-04-15': '2026-05-01', '2026-07-15': '2026-08-03'}


def decision(events):
    first = events[0]
    ticker, day = first['ticker'], first['ex_dividend_date']
    types = {e['distribution_type'] for e in events}
    if len(events) != 2 or len({e['id'] for e in events}) != 2:
        raise ValueError('Expected two distinct event IDs')
    if ticker == 'FCX' and day in FCX_DATES and types == {'recurring', 'irregular'}:
        if all(Decimal(str(e['cash_amount'])) == Decimal('0.075') and e['pay_date'] == FCX_DATES[day] for e in events):
            return 'KEEP_SEPARATE_COMPONENTS', 'Base and variable dividends; total USD 0.15 per eligible share', FCX
    if ticker == 'F' and day == '2025-02-18' and types == {'recurring', 'supplemental'}:
        if all(Decimal(str(e['cash_amount'])) == Decimal('0.15') and e['pay_date'] == '2025-03-03' for e in events):
            return 'KEEP_SEPARATE_COMPONENTS', 'Regular and supplemental dividends; total USD 0.30. Provider declaration dates differ; not corrected.', FORD + ' ; ' + FORD_DATES
    if ticker == 'TEL' and day == '2024-11-22':
        return 'HOLD_FOR_REVIEW', 'Issuer supports one USD 0.65 payment; two provider IDs and adjustment factors need resolution. Do not sum both or select one arbitrarily.', TEL
    raise ValueError('Pair differs from reviewed evidence')


def main():
    manifest = json.loads((SNAPSHOT / 'manifest.json').read_text())
    payload = checked_file(SNAPSHOT / 'dividends.jsonl', manifest['dividends']['sha256'])
    groups = defaultdict(list)
    for line in payload.decode().splitlines():
        record = json.loads(line)
        e = record['event']
        groups[(e['ticker'], e['ex_dividend_date'], str(e['cash_amount']), e['currency'])].append(record)
    rows = []
    pairs = [g for g in groups.values() if len(g) > 1]
    if len(pairs) != 10:
        raise ValueError('Expected ten saved pairs; inspect changed input')
    for group in pairs:
        events = [r['event'] for r in group]
        status, reason, sources = decision(events)
        for record in group:
            e = record['event']
            rows.append({'event_id': e['id'], 'ticker': e['ticker'], 'ex_dividend_date': e['ex_dividend_date'],
                'cash_amount': e['cash_amount'], 'distribution_type': e['distribution_type'],
                'decision': status, 'reason': reason, 'evidence_urls': sources,
                'source_file': record['source_file'], 'source_row_number': record['source_row_number']})
    folder = ROOT / 'data/corporate_action_reviews' / uuid4().hex
    folder.mkdir(parents=True)
    output = folder / 'dividend_pair_decisions.csv'
    with output.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {'reviewed_at': datetime.now(timezone.utc).isoformat(), 'snapshot': SNAPSHOT.name,
        'input_sha256': hashlib.sha256(payload).hexdigest(), 'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
        'pairs': len(pairs), 'event_decisions': dict(Counter(r['decision'] for r in rows)),
        'scope': 'Review of apparent duplicate payments only; not approval of account eligibility, historical knowledge timing, or every source field.',
        'applied_to_snowflake': False}
    (folder / 'manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    print(f'Decisions: {output}')


if __name__ == '__main__':
    main()
