"""Download daily prices for our saved stock universe, with resume support."""

import argparse
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from getpass import getpass
import hashlib
import json
import os
import re
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo


UNIVERSE = Path(__file__).resolve().parent / "config" / "stock_universe.csv"
# Keep a day inside the rolling two-year entitlement and exclude today.
TODAY = datetime.now(ZoneInfo("America/New_York")).date()
try:
    anniversary = TODAY.replace(year=TODAY.year - 2)
except ValueError:  # February 29 has no anniversary in a non-leap year.
    anniversary = date(TODAY.year - 2, 2, 28)
START = (anniversary + timedelta(days=1)).isoformat()
END = (TODAY - timedelta(days=1)).isoformat()
MAX_BYTES = 5_000_000


def read_symbols():
    with UNIVERSE.open(encoding="utf-8", newline="") as file:
        symbols = [row["Symbol"].strip() for row in csv.DictReader(file)]
    if not symbols or len(set(symbols)) != len(symbols):
        raise ValueError("Ticker list is empty or contains duplicates")
    for symbol in symbols:
        if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)?", symbol):
            raise ValueError(f"Unsupported ticker format: {symbol}")
    return symbols


def fetch(symbol, api_key, start=START, end=END):
    url = f"https://api.massive.com/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}"
    # Keep the prices as traded, without split adjustments.
    url += "?adjusted=false&sort=asc&limit=50000"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "NorthbridgeLearning/1.0",
    }
    request = Request(url, headers=headers)

    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read(MAX_BYTES + 1)
    except HTTPError as error:
        messages = {
            401: "API key was not accepted",
            403: "account cannot access this date range",
            429: "rate limit reached; wait a minute before retrying",
        }
        message = messages.get(error.code, f"provider returned HTTP {error.code}")
        raise RuntimeError(message) from None
    except (URLError, TimeoutError):
        raise RuntimeError("Could not reach Massive; check your connection and retry") from None
    # Reading one extra byte lets us detect a response that was cut short.
    if len(payload) > MAX_BYTES:
        raise ValueError("Response exceeds the size limit")
    return payload


def inspect_bars(payload, symbol, start=START, end=END):
    """Check the response and return its row count and date range."""
    data = json.loads(payload, parse_float=Decimal)
    if not isinstance(data, dict) or data.get("status") != "OK":
        raise ValueError(f"{symbol}: provider did not return an OK response")
    if data.get("ticker") != symbol:
        raise ValueError(f"{symbol}: response contains a different ticker")
    if data.get("adjusted") is not False:
        raise ValueError(f"{symbol}: expected unadjusted prices")
    if data.get("next_url"):
        raise ValueError("Response needs pagination; do not treat this snapshot as complete")
    bars = data.get("results")
    if not isinstance(bars, list) or not bars:
        raise ValueError(f"{symbol}: no daily prices returned")
    if data.get("resultsCount") != len(bars):
        raise ValueError(f"{symbol}: result count does not match the returned rows")

    dates = []
    market_timezone = ZoneInfo("America/New_York")
    required_fields = {"t", "o", "h", "l", "c", "v"}

    for bar in bars:
        if not isinstance(bar, dict) or not required_fields.issubset(bar):
            raise ValueError(f"{symbol}: missing daily bar fields")
        if type(bar["t"]) is not int:
            raise ValueError(f"{symbol}: timestamp must be integer milliseconds")
        timestamp = datetime.fromtimestamp(bar["t"] / 1000, timezone.utc)
        day = timestamp.astimezone(market_timezone).date().isoformat()
        if day < start or day > end:
            raise ValueError(f"{symbol}: date falls outside the requested range")
        if dates and day <= dates[-1]:
            raise ValueError(f"{symbol}: duplicate or unordered trading date")

        for field in ("o", "h", "l", "c", "v"):
            value = bar[field]
            if type(value) not in (int, Decimal):
                raise ValueError(f"{symbol}: {field} must be numeric")
            if not Decimal(value).is_finite():
                raise ValueError(f"{symbol}: {field} must be finite")

        opening = bar["o"]
        high = bar["h"]
        low = bar["l"]
        close = bar["c"]

        if low <= 0 or not low <= opening <= high or not low <= close <= high:
            raise ValueError(f"{symbol}: prices do not fit the daily high and low")
        if bar["v"] < 0:
            raise ValueError(f"{symbol}: volume cannot be negative")
        dates.append(day)

    return {
        "rows": len(bars),
        "first_date": dates[0],
        "last_date": dates[-1],
    }


def write_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def download(root, api_key, symbols=None, resume=None):
    if not api_key.strip():
        raise ValueError("An API key is required")
    if resume:
        folder = Path(resume)
        plan = json.loads((folder / "request.json").read_text(encoding="utf-8"))
        files = json.loads((folder / "progress.json").read_text(encoding="utf-8"))
        symbols = plan["symbols"]
        # Check before using saved names as filenames or request paths.
        for symbol in symbols:
            if not re.fullmatch(r"[A-Z][A-Z0-9]*(?:[.-][A-Z0-9]+)?", symbol):
                raise ValueError("Saved request contains an invalid ticker")
    else:
        symbols = list(symbols) if symbols is not None else read_symbols()
        folder = root / uuid4().hex
        folder.mkdir(parents=True, exist_ok=False)
        plan = {"symbols": symbols, "start": START, "end": END}
        if UNIVERSE.exists():
            (folder / "stock_universe.csv").write_bytes(UNIVERSE.read_bytes())
        write_json(folder / "request.json", plan)
        files = {}
        write_json(folder / "progress.json", files)

    start, end = plan["start"], plan["end"]
    print(f"{len(symbols)} tickers | {start} to {end}", flush=True)
    print(f'Resume command: python historical_prices.py --resume "{folder}"', flush=True)
    total_rows = 0
    requested = False

    for index, symbol in enumerate(symbols):
        filename = f"{symbol}.json"
        if filename in files:
            payload = (folder / filename).read_bytes()
            if hashlib.sha256(payload).hexdigest() != files[filename]["sha256"]:
                raise ValueError(f"Saved file changed: {filename}")
            summary = inspect_bars(payload, symbol, start, end)
            total_rows += summary["rows"]
            print(f"{index + 1}/{len(symbols)} {symbol}: already saved", flush=True)
            continue

        if requested:
            # The free account allows five requests per minute.
            time.sleep(13)

        payload = fetch(symbol, api_key, start, end)
        requested = True
        received_at = datetime.now(timezone.utc).isoformat()
        # Preserve what arrived, even if a later check fails.
        (folder / filename).write_bytes(payload)
        summary = inspect_bars(payload, symbol, start, end)
        files[filename] = {
            "rows": summary["rows"],
            "first_date": summary["first_date"],
            "last_date": summary["last_date"],
            "instrument": f"{symbol}.US",
            "received_at_utc": received_at,
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        total_rows += summary["rows"]
        write_json(folder / "progress.json", files)
        print(f"{index + 1}/{len(symbols)} {symbol}: saved {summary['rows']} daily bars", flush=True)

    # Write this last: its presence means all requested downloads passed the checks.
    manifest = {
        "source_system": "massive",
        "requested_from": start,
        "requested_to": end,
        "symbols": symbols,
        "ticker_count": len(symbols),
        "timespan": "day",
        "price_basis": "unadjusted",
        "currency": "USD",
        "files": files,
        "row_count": total_rows,
        "documentation": "https://massive.com/docs/rest/stocks/aggregates/custom-bars",
        "calendar_completeness_checked": False,
    }
    manifest_path = folder / "manifest.json"
    write_json(manifest_path, manifest)
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", type=Path, help="Continue a previously started snapshot folder")
    args = parser.parse_args()
    key = os.environ.get("MASSIVE_API_KEY")
    if not key:
        key = getpass("Massive API key (hidden): ")

    output_folder = Path(__file__).resolve().parent / "data" / "historical_prices"
    try:
        folder = download(output_folder, key, resume=args.resume)
    except (ValueError, RuntimeError) as error:
        message = f"Download stopped: {error}. Any partial folder has no completion manifest."
        raise SystemExit(message) from None
    except KeyboardInterrupt:
        raise SystemExit("Stopped. Use the printed resume command to continue this download.") from None
    print(f"Historical snapshot saved: {folder}")


if __name__ == "__main__":
    main()
