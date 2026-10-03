"""Prepare verified corporate-action files and review history for Snowflake."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = '7962b1659329451b86a5eb288fd7d61e'
REVIEWS = [
 ('0a2042dd095e4a348a1dd75064a87658', 'bny_decisions.csv', 'decision_sha256', 'dividends_sha256'),
 ('26e32fc523e24ab08a0c479c0369e423', 'dividend_pair_decisions.csv', 'output_sha256', 'input_sha256'),
 ('33fbc11bbd4740e5905b49cbcc3060b4', 'tel_reviewed_event.json', 'output_sha256', 'input_sha256'),
]


def checked(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'File fingerprint changed: {path}')
    return raw


def main():
    source = ROOT / 'data/corporate_actions' / SNAPSHOT
    manifest = json.loads((source / 'manifest.json').read_text())
    if manifest['status'] != 'COMPLETE':
        raise ValueError('Download is incomplete')
    actions = []
    for kind, count in [('splits', 24), ('dividends', 3247)]:
        raw = checked(source / (kind + '.jsonl'), manifest[kind]['sha256'])
        records = [json.loads(line) for line in raw.decode().splitlines()]
        if len(records) != count or len({r['event']['id'] for r in records}) != count:
            raise ValueError('Unexpected event count or duplicate IDs')
        actions.extend({'action_type': kind, **r} for r in records)
    reviews = []
    for review_id, filename, hash_field, input_field in REVIEWS:
        folder = ROOT / 'data/corporate_action_reviews' / review_id
        evidence = json.loads((folder / 'manifest.json').read_text())
        if evidence[input_field] != manifest['dividends']['sha256']:
            raise ValueError('Review refers to another dividend snapshot')
        raw = checked(folder / filename, evidence[hash_field])
        records = list(csv.DictReader(raw.decode().splitlines())) if filename.endswith('.csv') else [json.loads(raw)]
        reviews.extend({'review_id': review_id, 'review_file': filename, 'review_manifest': evidence,
                        'decision': record} for record in records)
    content = {name: ''.join(json.dumps(r) + '\n' for r in records).encode()
               for name, records in [('actions.jsonl', actions), ('reviews.jsonl', reviews)]}
    batch = hashlib.sha256(content['actions.jsonl'] + content['reviews.jsonl']).hexdigest()[:32]
    folder = ROOT / 'data/corporate_action_loads' / batch
    folder.mkdir(parents=True, exist_ok=True)
    for name, raw in content.items():
        path = folder / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError('Existing load file differs')
        path.write_bytes(raw)
    (folder / 'manifest.json').write_text(json.dumps({'snapshot': SNAPSHOT, 'load_id': batch,
        'actions': len(actions), 'reviews': len(reviews),
        'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in content.items()}}, indent=2))
    statements = ['USE ROLE SYSADMIN;', 'USE WAREHOUSE COMPUTE_WH;']
    for filename, table in [('actions.jsonl', 'CORPORATE_ACTIONS'), ('reviews.jsonl', 'CORPORATE_ACTION_REVIEWS')]:
        statements.extend([
            f"PUT '{(folder / filename).as_uri()}' @NORTHBRIDGE_DEV.RAW.CORPORATE_ACTIONS_STAGE/{batch}/ AUTO_COMPRESS=TRUE OVERWRITE=FALSE;",
            f"COPY INTO NORTHBRIDGE_DEV.RAW.{table} (payload, snapshot_id, load_id, source_file, source_row_number)\n"
            f"FROM (SELECT t.$1, '{SNAPSHOT}', '{batch}', METADATA$FILENAME, METADATA$FILE_ROW_NUMBER\n"
            f"FROM @NORTHBRIDGE_DEV.RAW.CORPORATE_ACTIONS_STAGE/{batch}/ t)\n"
            f"FILES=('{filename}.gz') FILE_FORMAT=(FORMAT_NAME='NORTHBRIDGE_DEV.RAW.CORPORATE_ACTIONS_JSON') ON_ERROR=ABORT_STATEMENT FORCE=FALSE;"])
    statements.extend([
        f"SELECT payload:action_type::varchar AS action_type, COUNT(*) AS records, COUNT(DISTINCT payload:event:id::varchar) AS distinct_events FROM NORTHBRIDGE_DEV.RAW.CORPORATE_ACTIONS WHERE load_id='{batch}' GROUP BY 1;",
        f"SELECT payload:review_id::varchar AS review_id, COUNT(*) AS records FROM NORTHBRIDGE_DEV.RAW.CORPORATE_ACTION_REVIEWS WHERE load_id='{batch}' GROUP BY 1;"])
    (ROOT / 'snowflake/20_load_corporate_actions.sql').write_text('\n\n'.join(statements) + '\n')
    print(f'Prepared {len(actions)} events and {len(reviews)} review records. Load ID: {batch}')


if __name__ == '__main__':
    main()
