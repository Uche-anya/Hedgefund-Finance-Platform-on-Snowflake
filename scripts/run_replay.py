"""Load the saved replay and broker statement, build dbt and check both results."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = 'sim-dividend-a48996d29c0473a090db3b9f'
SCENARIO = 'sim-replay-406bbef8179cdbb0a3dd6df3'
BROKER_DELIVERY = 'sim-broker-42a53a52c3913f138bf0ba35'


def verify_inputs(root):
    folder = root / 'data/replays' / DELIVERY
    raw = (folder / 'manifest.json').read_bytes()
    manifest = json.loads(raw)
    if manifest['delivery_id'] != DELIVERY or manifest['scenario_id'] != SCENARIO:
        raise ValueError('Unexpected replay delivery')
    config = manifest['config']
    files = [
        (folder / 'records.jsonl', manifest['files']['records.jsonl']),
        (root / config['price_snapshot'] / 'prices.csv', config['price_sha256']),
        (root / config['calendar'], config['calendar_sha256']),
    ]
    for path, expected in files:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Saved input changed: {path.name}')
    broker_folder = root / 'data/broker_statements' / BROKER_DELIVERY
    broker_raw = (broker_folder / 'manifest.json').read_bytes()
    broker = json.loads(broker_raw)
    if broker['delivery_id'] != BROKER_DELIVERY or broker['scenario_id'] != SCENARIO:
        raise ValueError('Unexpected broker delivery')
    broker_file = broker_folder / 'positions.jsonl'
    if hashlib.sha256(broker_file.read_bytes()).hexdigest() != broker['files']['positions.jsonl']:
        raise ValueError('Saved broker positions changed')
    return {
        'delivery_id': DELIVERY,
        'manifest_sha256': hashlib.sha256(raw).hexdigest(),
        'broker_delivery_id': BROKER_DELIVERY,
        'broker_manifest_sha256': hashlib.sha256(broker_raw).hexdigest(),
    }


def run_pipeline(root=ROOT):
    folder = root / 'data/replay_runs' / uuid4().hex
    folder.mkdir(parents=True)
    report = folder / 'run.json'
    record = {'status': 'RUNNING', 'started_at': datetime.now(timezone.utc).isoformat(),
              'steps': []}
    code = 1
    try:
        record['inputs'] = verify_inputs(root)
        python = root / '.venv/dbt/Scripts/python.exe'
        if not python.is_file():
            raise FileNotFoundError('The dbt Python environment is missing')
        steps = [
            ('load_inputs', [str(python), 'scripts/load_daily_inputs.py']),
            ('build_and_test', [str(python), 'scripts/dbt_dev.py', 'build']),
            ('check_financials', [str(python), 'scripts/check_replay.py']),
            ('check_reconciliation', [str(python), 'scripts/check_broker_reconciliation.py']),
            ('check_extended_sources', [str(python), 'scripts/check_extended_sources.py']),
            ('publish_nav', [str(python), 'scripts/publish_nav.py']),
            ('check_publication', [str(python), 'scripts/check_nav_publication.py']),
        ]
        for name, command in steps:
            print(f'\n{name}', flush=True)
            step = {'name': name, 'started_at': datetime.now(timezone.utc).isoformat()}
            record['steps'].append(step)
            report.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
            code = subprocess.run(command, cwd=root).returncode
            step['exit_code'] = code
            step['finished_at'] = datetime.now(timezone.utc).isoformat()
            if code:
                record['status'] = 'FAILED'
                break
        else:
            record['status'] = 'SUCCEEDED'
    except KeyboardInterrupt:
        code = 130
        record['status'] = 'INTERRUPTED'
    except (OSError, ValueError, KeyError) as error:
        code = 1
        record['status'] = 'FAILED'
        record['error'] = str(error)
        print(error, flush=True)
    finally:
        record['exit_code'] = code
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        report.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print(f"Run {record['status']}. Record: {report}", flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(run_pipeline())
