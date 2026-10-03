"""Save Massive split and dividend pages and extract candidate stock events."""

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / 'data/assembled_prices/fb25ddd9838840488e4c8b971ff7e0ae/prices.csv'
DATES = {'splits': 'execution_date', 'dividends': 'ex_dividend_date'}


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def clean_url(url, kind):
    parts = urlsplit(url)
    if (parts.scheme != 'https' or parts.netloc != 'api.massive.com'
            or parts.path != '/stocks/v1/' + kind or parts.fragment):
        raise ValueError('Unexpected pagination URL')
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() != 'apikey']
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ''))


def fetch(url, key):
    request = Request(url, headers={'Authorization': 'Bearer ' + key})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                raw = response.read(20_000_001)
            if len(raw) > 20_000_000:
                raise ValueError('Response exceeds 20 MB')
            result = json.loads(raw)
            if result.get('status') != 'OK' or not isinstance(result.get('results'), list):
                raise ValueError('Provider did not return an OK results list')
            return result
        except HTTPError as error:
            if error.code == 429 and attempt < 2:
                print('Rate limit reached; waiting 30 seconds.', flush=True)
                time.sleep(30)
                continue
            raise RuntimeError(f'Massive HTTP {error.code}; check key and date-range access') from None
        except (URLError, TimeoutError):
            raise RuntimeError('Could not reach Massive; resume the saved download') from None


def download(folder, key):
    plan = json.loads((folder / 'request.json').read_text())
    manifest_path = folder / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    symbols = set(plan['symbols'])
    requested = False
    for kind, date_field in DATES.items():
        query = {date_field + '.gte': plan['start'], date_field + '.lte': plan['end'],
                 'limit': 5000, 'sort': date_field + '.asc'}
        url = 'https://api.massive.com/stocks/v1/' + kind + '?' + urlencode(query)
        page = 0
        seen_urls, seen_ids, candidates = set(), set(), []
        while url:
            url = clean_url(url, kind)
            if url in seen_urls:
                raise ValueError('Repeated pagination URL')
            seen_urls.add(url)
            page += 1
            name = f'{kind}_{page:04d}.json'
            path = folder / name
            if name in manifest['pages']:
                raw = path.read_bytes()
                entry = manifest['pages'][name]
                if hashlib.sha256(raw).hexdigest() != entry['sha256'] or entry['url'] != url:
                    raise ValueError('Saved page changed or does not match request')
                result = json.loads(raw)
            else:
                if requested:
                    time.sleep(13)
                result = fetch(url, key)
                requested = True
                # Pagination URLs can carry credentials; never persist those credentials.
                if result.get('next_url'):
                    result['next_url'] = clean_url(result['next_url'], kind)
                save(path, result)
                manifest['pages'][name] = {
                    'url': url, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'retrieved_at': datetime.now(timezone.utc).isoformat()}
                save(manifest_path, manifest)
            for index, row in enumerate(result['results'], 1):
                event_id, day = row.get('id'), row.get(date_field)
                if not event_id or not day or not plan['start'] <= day <= plan['end']:
                    raise ValueError(f'{name}: missing event ID or out-of-range date')
                if event_id in seen_ids:
                    raise ValueError(f'{kind}: duplicate event ID across pages')
                seen_ids.add(event_id)
                if row.get('ticker') in symbols:
                    candidates.append({'source_file': name, 'source_row_number': index,
                                       'identity_status': 'ticker_match_requires_review', 'event': row})
            print(f'{kind} page {page}: {len(result["results"])} records; {len(candidates)} stock candidates so far', flush=True)
            url = result.get('next_url')
        output = folder / (kind + '.jsonl')
        output.write_text(''.join(json.dumps(row) + '\n' for row in candidates), encoding='utf-8')
        manifest[kind] = {'provider_rows': len(seen_ids), 'candidate_rows': len(candidates),
                          'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
        save(manifest_path, manifest)
    manifest['status'] = 'COMPLETE'
    save(manifest_path, manifest)
    print(f'Corporate actions saved: {folder}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume', type=Path)
    parser.add_argument('--start', help='Override default rolling free-tier start (YYYY-MM-DD)')
    args = parser.parse_args()
    if args.resume and args.start:
        parser.error('Use --resume without --start')
    key = os.environ.get('MASSIVE_API_KEY')
    if not key:
        if not sys.stdin.isatty():
            raise ValueError('Run in your terminal to enter the Massive API key privately')
        key = getpass('Massive API key (hidden): ')
    if not key.strip():
        raise ValueError('An API key is required')
    if args.resume:
        folder = args.resume.resolve()
    else:
        symbols, days = set(), set()
        with PRICES.open(newline='', encoding='utf-8') as file:
            for row in csv.DictReader(file):
                symbols.add(row['source_ticker'])
                days.add(row['valuation_date'])
        today = datetime.now(timezone.utc).date()
        try:
            anniversary = today.replace(year=today.year - 2)
        except ValueError:
            anniversary = date(today.year - 2, 2, 28)
        start = args.start or max(min(days), (anniversary + timedelta(days=1)).isoformat())
        end = max(days)
        if date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError('Start date is after the saved price history')
        folder = ROOT / 'data/corporate_actions' / uuid4().hex
        folder.mkdir(parents=True)
        save(folder / 'request.json', {'start': start, 'end': end, 'price_start': min(days),
             'symbols': sorted(symbols), 'price_sha256': hashlib.sha256(PRICES.read_bytes()).hexdigest(),
             'note': 'Ticker candidates only; rolling access may exclude earliest price dates. Historical facts as retrieved now, not point-in-time announcements.'})
        save(folder / 'manifest.json', {'status': 'INCOMPLETE', 'source_system': 'massive', 'pages': {}})
    print(f'Snapshot folder: {folder}', flush=True)
    print(f'Resume: python -m data_extraction.corporate_actions --resume "{folder}"', flush=True)
    plan = json.loads((folder / 'request.json').read_text())
    print(f'Requesting {plan["start"]} through {plan["end"]}; price history starts {plan["price_start"]}', flush=True)
    download(folder, key)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError) as error:
        print(f'Download stopped: {error}', file=sys.stderr)
        raise SystemExit(1)
