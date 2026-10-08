"""Turn one saved Massive trading day into a checked Snowflake CSV."""

import argparse
import csv
from decimal import Decimal
import hashlib
import io
import json
from pathlib import Path

from data_extraction.assemble_prices import FIELDS, validate_rows
from data_extraction.historical_prices import inspect_bars
from data_extraction.repair_bny_history import bar_date


ROOT = Path(__file__).resolve().parents[1]


def write_once(path, content):
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"Saved file changed: {path}")
    else:
        path.write_bytes(content)


def prepare(snapshot, config_path):
    snapshot = snapshot.resolve()
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    day = manifest["requested_from"]
    tickers = config["tickers"]
    if manifest["requested_to"] != day or manifest["symbols"] != tickers:
        raise ValueError("Download does not match one day and this scenario's tickers")
    if manifest["ticker_count"] != len(tickers) or manifest["row_count"] != len(tickers):
        raise ValueError("Expected one daily bar for every traded ticker")

    rows = []
    for ticker in tickers:
        name = ticker + ".json"
        raw = (snapshot / name).read_bytes()
        saved = manifest["files"][name]
        if hashlib.sha256(raw).hexdigest() != saved["sha256"]:
            raise ValueError(f"Changed provider response: {name}")
        if inspect_bars(raw, ticker, day, day)["rows"] != 1:
            raise ValueError(f"Expected one bar for {ticker}")
        bar = json.loads(raw, parse_float=Decimal)["results"][0]
        row = {
            "valuation_date": bar_date(bar),
            "universe_ticker": ticker,
            "instrument_id": "",
            "share_class_figi": "",
            "source_ticker": ticker,
            "currency": "USD",
            "open": str(bar["o"]),
            "high": str(bar["h"]),
            "low": str(bar["l"]),
            "close_price": str(bar["c"]),
            "volume": str(bar["v"]),
            "price_basis": "unadjusted",
            "identity_status": "provider_ticker_only",
            "source_system": "massive",
            "input_file": (snapshot / name).relative_to(ROOT).as_posix(),
            "input_row_number": "1",
        }
        validate_rows(ticker, [row], [day])
        rows.append(row)

    output = ROOT / "data/daily_prices" / snapshot.name
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "prices.csv"
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    content = buffer.getvalue().encode("utf-8")
    write_once(csv_path, content)
    delivery_id = "daily-prices-" + hashlib.sha256(content).hexdigest()[:24]
    receipt = {
        "delivery_id": delivery_id,
        "valuation_date": day,
        "record_count": len(rows),
        "source_snapshot": snapshot.relative_to(ROOT).as_posix(),
        "source_manifest_sha256": hashlib.sha256((snapshot / "manifest.json").read_bytes()).hexdigest(),
        "files": {"prices.csv": hashlib.sha256(content).hexdigest()},
    }
    write_once(output / "manifest.json",
               (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode())
    print(f"{day}: prepared {len(rows)} prices in {output}")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config/two_year_replay_v2.json")
    args = parser.parse_args()
    prepare(args.snapshot, args.config)
