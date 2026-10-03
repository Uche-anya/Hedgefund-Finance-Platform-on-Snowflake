"""Inspect a saved corporate-action download without changing source data."""

import argparse
from collections import Counter
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

from data_extraction.corporate_actions import ROOT, PRICES, DATES, clean_url


def inspect(folder):
    request = json.loads((folder / 'request.json').read_text())
    manifest = json.loads((folder / 'manifest.json').read_text())
    errors, reviews = [], []
    def error(message):
        errors.append(message)
    def review(kind, event, reason):
        reviews.append({'kind': kind, 'event_id': event.get('id'), 'ticker': event.get('ticker'),
                        'date': event.get(DATES[kind]), 'reason': reason})
    def valid_date(value):
        try:
            return date.fromisoformat(value).isoformat() == value
        except (ValueError, TypeError):
            return False
    def positive(value):
        try:
            number = Decimal(str(value))
            return number.is_finite() and number > 0
        except InvalidOperation:
            return False

    if manifest.get('status') != 'COMPLETE':
        error('Manifest is not COMPLETE')
    if hashlib.sha256(PRICES.read_bytes()).hexdigest() != request['price_sha256']:
        error('Price snapshot hash mismatch')
    price_dates = set()
    with PRICES.open(newline='', encoding='utf-8') as file:
        for row in csv.DictReader(file):
            price_dates.add((row['source_ticker'], row['valuation_date']))
    symbols = set(request['symbols'])
    replay = json.loads((ROOT / 'config/replay_january.json').read_text())
    report = {'requested_start': request['start'], 'requested_end': request['end'],
              'price_start': request['price_start'], 'full_price_period_covered': request['start'] <= request['price_start'],
              'identity_note': 'Ticker/date matches are not proof of security identity.', 'datasets': {}}
    for kind, date_field in DATES.items():
        pages = sorted(name for name in manifest['pages'] if name.startswith(kind + '_'))
        candidates, provider_ids, duplicate_ids = [], set(), 0
        previous_next = None
        for index, name in enumerate(pages, 1):
            if name != f'{kind}_{index:04d}.json':
                error(f'{kind}: nonconsecutive page filenames')
            raw = (folder / name).read_bytes()
            entry = manifest['pages'][name]
            if hashlib.sha256(raw).hexdigest() != entry['sha256']:
                error(f'{name}: hash mismatch')
            if index > 1 and previous_next != entry['url']:
                error(f'{name}: pagination chain mismatch')
            page = json.loads(raw)
            if page.get('status') != 'OK':
                error(f'{name}: provider status is not OK')
            previous_next = clean_url(page['next_url'], kind) if page.get('next_url') else None
            for number, event in enumerate(page['results'], 1):
                event_id = event.get('id')
                if not event_id or event_id in provider_ids:
                    duplicate_ids += 1
                provider_ids.add(event_id)
                if event.get('ticker') in symbols:
                    candidates.append({'source_file': name, 'source_row_number': number,
                                       'identity_status': 'ticker_match_requires_review', 'event': event})
        if not pages or previous_next:
            error(f'{kind}: missing pages or unconsumed next page')
        raw = (folder / (kind + '.jsonl')).read_bytes()
        saved = [json.loads(line) for line in raw.decode().splitlines()]
        if hashlib.sha256(raw).hexdigest() != manifest[kind]['sha256']:
            error(f'{kind}: candidate file hash mismatch')
        if saved != candidates:
            error(f'{kind}: candidates differ from source-page selection')
        if len(saved) != manifest[kind]['candidate_rows'] or len(provider_ids) != manifest[kind]['provider_rows']:
            error(f'{kind}: manifest counts differ')
        if duplicate_ids:
            error(f'{kind}: {duplicate_ids} missing/duplicate provider IDs')
        types, currencies, replay_events = Counter(), Counter(), []
        dates = []
        economic_keys = Counter()
        for record in saved:
            event = record['event']
            day = event.get(date_field)
            if not valid_date(day) or not request['start'] <= day <= request['end']:
                error(f'{kind} {event.get("id")}: invalid or out-of-range event date')
                continue
            dates.append(day)
            types[event.get('adjustment_type' if kind == 'splits' else 'distribution_type', 'missing')] += 1
            if (event['ticker'], day) not in price_dates:
                review(kind, event, 'No matching source ticker and date in saved prices; review calendar and identity')
            if kind == 'splits':
                if not positive(event.get('split_from')) or not positive(event.get('split_to')):
                    error(f'{kind} {event.get("id")}: invalid split ratio')
                if event.get('adjustment_type') != 'forward_split':
                    review(kind, event, 'Non-forward split needs separate accounting review')
                economic_keys[(event['ticker'], day, event.get('split_from'), event.get('split_to'))] += 1
            else:
                currencies[event.get('currency', 'missing')] += 1
                if not positive(event.get('cash_amount')):
                    error(f'{kind} {event.get("id")}: missing, zero or invalid cash amount')
                if event.get('currency') != 'USD':
                    review(kind, event, 'Missing or non-USD currency')
                for field in ['declaration_date', 'record_date', 'pay_date']:
                    if not valid_date(event.get(field)):
                        review(kind, event, 'Missing or invalid ' + field)
                if valid_date(event.get('pay_date')) and event['pay_date'] < day:
                    review(kind, event, 'Payment date precedes ex-date; check special distribution rules')
                if event.get('distribution_type') != 'recurring':
                    review(kind, event, 'Non-recurring distribution needs review')
                economic_keys[(event['ticker'], day, event.get('cash_amount'), event.get('currency'))] += 1
            if event['ticker'] in replay['tickers'] and replay['start_date'] <= day <= replay['end_date']:
                replay_events.append(event)
        for record in saved:
            event = record['event']
            fields = ('split_from', 'split_to') if kind == 'splits' else ('cash_amount', 'currency')
            key = (event.get('ticker'), event.get(date_field), *(event.get(f) for f in fields))
            if economic_keys[key] > 1:
                review(kind, event, 'Same ticker/date/amount or ratio as another event; retain until reviewed')
        report['datasets'][kind] = {'pages': len(pages), 'provider_rows': len(provider_ids),
            'candidate_rows': len(saved), 'candidate_tickers': len({r['event']['ticker'] for r in saved}),
            'first_event': min(dates) if dates else None, 'last_event': max(dates) if dates else None,
            'types': dict(types), 'currencies': dict(currencies),
            'repeated_economic_keys': sum(n - 1 for n in economic_keys.values() if n > 1),
            'january_replay_events': replay_events}
    report['errors'] = errors
    report['review_reasons'] = dict(Counter(r['reason'] for r in reviews))
    report['status'] = 'ERRORS_FOUND' if errors else 'FILES_VERIFIED_REVIEW_PENDING'
    output = folder / 'inspection'
    output.mkdir(exist_ok=True)
    (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    with (output / 'review.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=['kind', 'event_id', 'ticker', 'date', 'reason'])
        writer.writeheader()
        writer.writerows(reviews)
    print(json.dumps(report, indent=2))
    print(f'Review files: {output}')
    return 1 if errors else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    raise SystemExit(inspect(parser.parse_args().folder))
