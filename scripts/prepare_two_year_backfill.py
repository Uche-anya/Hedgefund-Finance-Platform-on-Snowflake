"""Pack the remaining daily files for one historical Snowflake COPY."""

import hashlib
import json
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_two_year_replay import audit
from scripts.close_daily_pilot import saved_delivery
from simulation.daily_oms import write_once


def make_file(folder, daily_root, filename, days, prefix):
    parts = []
    sources = {}
    for day in days:
        manifest, rows = saved_delivery(daily_root / day, filename)
        delivery_id = f"{prefix}-{day.replace('-', '')}"
        if manifest['delivery_id'] != delivery_id:
            raise ValueError(f'Wrong delivery ID for {day}')
        raw = (daily_root / day / filename).read_bytes()
        parts.append(raw)
        sources[delivery_id] = {'sha256': hashlib.sha256(raw).hexdigest(),
                                'rows': len(rows)}
    body = b''.join(parts)
    write_once(folder / filename, body)
    return {'file': filename, 'sha256': hashlib.sha256(body).hexdigest(),
            'rows': sum(item['rows'] for item in sources.values()),
            'deliveries': sources}


def prepare(config_path=ROOT / 'config/two_year_replay.json',
            pilot_path=ROOT / 'config/two_year_pilot.json'):
    report = audit(config_path)
    config = json.loads(config_path.read_text(encoding='utf-8'))
    pilot = json.loads(pilot_path.read_text(encoding='utf-8'))
    scenario = config['scenario_id']
    if scenario != pilot['scenario_id'] or config['start_date'] != pilot['start_date']:
        raise ValueError('The full run must extend the existing pilot scenario')
    oms_root = ROOT / 'data/daily_oms' / scenario
    settlement_root = ROOT / 'data/daily_settlements' / scenario
    trade_days = sorted(path.name for path in oms_root.iterdir() if path.is_dir())
    due_days = sorted(path.name for path in settlement_root.iterdir() if path.is_dir())
    if len(trade_days) != report['trade_dates'] or len(due_days) != report['settlement_dates']:
        raise ValueError('Daily file count changed after audit')
    pilot_due_end = due_days[trade_days.index(pilot['end_date'])]
    remaining_trades = [day for day in trade_days if day > pilot['end_date']]
    remaining_due = [day for day in due_days if day > pilot_due_end]
    folder = ROOT / 'data/two_year_backfill' / scenario
    oms = make_file(folder, oms_root, 'oms.jsonl', remaining_trades, 'oms-' + scenario)
    settlements = make_file(folder, settlement_root, 'settlements.jsonl',
                            remaining_due, 'settlement-' + scenario)
    manifest = {'scenario_id': scenario, 'pilot_last_trade_date': pilot['end_date'],
                'pilot_last_settlement_date': pilot_due_end,
                'oms': oms, 'settlements': settlements}
    write_once(folder / 'manifest.json',
               (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode())
    print(f"Backfill prepared: {len(oms['deliveries'])} OMS days / {oms['rows']} events; "
          f"{len(settlements['deliveries'])} custodian days / {settlements['rows']} events")
    print(folder)
    return folder


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config/two_year_replay.json')
    parser.add_argument('--pilot-config', type=Path, default=ROOT / 'config/two_year_pilot.json')
    args = parser.parse_args()
    prepare(args.config.resolve(), args.pilot_config.resolve())
