"""Look up the securities behind BK and BNY on dates around the price gap."""

import csv
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


CHECKS = (
    ("BNY", "2026-02-06"),
    ("BK", "2026-02-06"),
    ("BK", "2026-05-20"),
    ("BNY", "2026-05-21"),
)
FIELDS = ("name", "cik", "composite_figi", "share_class_figi",
          "type", "primary_exchange", "currency_name", "active")


def fetch_details(ticker, day, key):
    url = f"https://api.massive.com/v3/reference/tickers/{ticker}?date={day}"
    request = Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read(1_000_001)
    except HTTPError as error:
        raise RuntimeError(
            f"{ticker} on {day}: HTTP {error.code}. "
            "Check API access; for 429, wait a minute before retrying."
        ) from None
    except (URLError, TimeoutError):
        raise RuntimeError(f"{ticker} on {day}: could not reach Massive") from None
    if len(payload) > 1_000_000:
        raise ValueError("Reference response is larger than expected")
    return payload


def read_identity(payload, ticker, day):
    data = json.loads(payload)
    if not isinstance(data, dict) or data.get("status") != "OK":
        raise ValueError(f"{ticker} on {day}: reference request did not succeed")
    details = data.get("results")
    if not isinstance(details, dict) or details.get("ticker") != ticker:
        raise ValueError(f"{ticker} on {day}: unexpected reference result")
    if not details.get("name"):
        raise ValueError(f"{ticker} on {day}: missing security name")

    row = {"requested_ticker": ticker, "as_of_date": day}
    for field in FIELDS:
        # Missing identifiers stay blank; never treat two blanks as a match.
        row[field] = details.get(field, "")
    return row


def check_identities(root, key, checks=CHECKS):
    if not key.strip():
        raise ValueError("An API key is required")
    folder = root / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    print(f"Saving reference evidence in {folder}", flush=True)
    rows = []
    requests = []
    for index, (ticker, day) in enumerate(checks):
        if index > 0:
            time.sleep(13)
        payload = fetch_details(ticker, day, key)
        filename = f"{ticker}_{day}.json"
        (folder / filename).write_bytes(payload)
        row = read_identity(payload, ticker, day)
        rows.append(row)
        requests.append({
            "ticker": ticker,
            "date": day,
            "file": filename,
            "received_at_utc": datetime.now(timezone.utc).isoformat(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })
        print(f"{ticker} on {day}: {row['name']}", flush=True)
        print(f"  CIK: {row['cik'] or 'missing'} | "
              f"Share-class FIGI: {row['share_class_figi'] or 'missing'}", flush=True)

    with (folder / "identities.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "source_system": "massive",
        "requests": requests,
        "documentation": "https://massive.com/docs/rest/stocks/tickers/ticker-overview",
        "review_status": "pending; no price mapping approved",
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Compare the {len(rows)} rows in {folder / 'identities.csv'}", flush=True)
    return folder


def main():
    key = os.environ.get("MASSIVE_API_KEY")
    if not key:
        key = getpass("Massive API key (hidden): ")
    root = Path(__file__).resolve().parents[1] / "data" / "reference_checks"
    try:
        check_identities(root, key)
    except (ValueError, RuntimeError) as error:
        raise SystemExit(f"Identity check stopped: {error}") from None


if __name__ == "__main__":
    main()
