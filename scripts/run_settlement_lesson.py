"""Reload the saved settlement deliveries and rebuild their dbt reports."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
DELIVERIES = {
    'a98ed87facdf46f6be0fc923d59b5975': 4,
    '2cfd3d50543c480dbbd15dae315c2cfa': 1,
}
SELECTOR = ('+settlement_exceptions settlement_report_history '
            'settlement_history_matches_current oms_executions_preserve_rows '
            'settlements_preserve_rows')


def verify_inputs(root):
    evidence = []
    for delivery, count in DELIVERIES.items():
        folder = root / 'data/simulator_settlements' / delivery
        manifest_file = folder / 'manifest.json'
        raw = manifest_file.read_bytes()
        manifest = json.loads(raw)
        if (manifest['delivery_id'] != delivery or manifest['event_count'] != count
                or len(manifest['files']) != count):
            raise ValueError(f'Unexpected delivery contents: {delivery}')
        for name, expected_hash in manifest['files'].items():
            if Path(name).name != name or not name.endswith('.jsonl'):
                raise ValueError('Expected a local JSONL filename')
            actual_hash = hashlib.sha256((folder / name).read_bytes()).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError(f'Input file changed: {name}')
        evidence.append({'delivery_id': delivery, 'event_count': count,
                         'manifest_sha256': hashlib.sha256(raw).hexdigest()})
    return evidence


def run_pipeline(root=ROOT):
    folder = root / 'data/pipeline_runs' / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    record = {'pipeline': 'settlement_lesson', 'status': 'RUNNING',
              'started_at': datetime.now(timezone.utc).isoformat(), 'steps': []}
    report = folder / 'run.json'
    code = 1
    try:
        record['inputs'] = verify_inputs(root)
        dbt_python = root / '.venv/dbt/Scripts/python.exe'
        if not dbt_python.is_file():
            raise FileNotFoundError('The dbt Python environment is missing')
        steps = [
            ('load_original_confirmations',
             [sys.executable, 'scripts/snow_admin.py', '--file', 'snowflake/16_settlement_events.sql']),
            ('load_late_confirmation',
             [sys.executable, 'scripts/snow_admin.py', '--file', 'snowflake/17_late_settlement.sql']),
            ('build_and_test_reports',
             [str(dbt_python), 'scripts/dbt_dev.py', 'build', '--select', SELECTOR]),
        ]
        for name, command in steps:
            print(f'\n{name}', flush=True)
            step = {'name': name, 'started_at': datetime.now(timezone.utc).isoformat()}
            record['steps'].append(step)
            report.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
            result = subprocess.run(command, cwd=root)
            step['exit_code'] = result.returncode
            step['finished_at'] = datetime.now(timezone.utc).isoformat()
            if result.returncode != 0:
                code = result.returncode
                record['status'] = 'FAILED'
                print(f'Stopped after {name}; later steps were not run.', flush=True)
                break
        else:
            code = 0
            record['status'] = 'SUCCEEDED'
    except KeyboardInterrupt:
        code = 130
        record['status'] = 'INTERRUPTED'
    except (OSError, ValueError, KeyError) as error:
        record['status'] = 'FAILED'
        record['error'] = str(error)
        print(f'Cannot complete the run: {error}', flush=True)
    finally:
        record['exit_code'] = code
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        report.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        print(f"Run {record['status']}. Record: {report}", flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(run_pipeline())
