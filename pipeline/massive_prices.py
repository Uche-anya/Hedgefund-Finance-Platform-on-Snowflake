"""Fetch one unadjusted US stock closing-price delivery from Massive."""

import argparse
import csv
import hashlib
import io
import json
import os
import time
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/"
FIELDS = ("valuation_date", "universe_ticker", "currency", "close_price",
          "price_basis", "source_system", "provider_request_id")
KEY_SERVICE = "northbridge/massive-api"


def read_api_key():
    key = (os.environ.get("MASSIVE_API_KEY") or "").strip()
    if key:
        return key
    from keyring.backends.Windows import WinVaultKeyring

    key = WinVaultKeyring().get_password(KEY_SERVICE, "massive")
    if not key:
        raise ValueError("Massive key missing; run scripts/save_massive_key.py")
    return key


def get_response(day, api_key):
    url = BASE_URL + day + "?adjusted=false&include_otc=false"
    request = Request(url, headers={"Authorization": "Bearer " + api_key,
                                    "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read(25_000_001)
            if len(body) > 25_000_000:
                raise ValueError("Massive response is unexpectedly large")
            return json.loads(body)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError("Massive returned HTTP {}".format(error.code)) from None
        except URLError:
            if attempt == 2:
                raise RuntimeError("Could not reach Massive") from None
        time.sleep(2 * (attempt + 1))


def price_rows(day, response):
    if response.get("status") != "OK" or response.get("adjusted") is not False:
        raise ValueError("Massive did not return an unadjusted daily summary")
    if response.get("next_url"):
        raise ValueError("Massive response has another page")
    bars = response.get("results")
    if not isinstance(bars, list) or not bars:
        raise ValueError("No market bars returned for {}".format(day))
    if response.get("resultsCount") != len(bars):
        raise ValueError("Massive result count does not match its bars")

    rows = {}
    for bar in bars:
        if not isinstance(bar, dict):
            raise ValueError("Bad bar in Massive summary")
        ticker = bar.get("T")
        if not isinstance(ticker, str) or not ticker or ticker in rows:
            raise ValueError("Missing or duplicate ticker in Massive summary")
        try:
            close = Decimal(str(bar["c"]))
        except (KeyError, InvalidOperation):
            raise ValueError("Bad close for {}".format(ticker)) from None
        if not close.is_finite() or close <= 0:
            raise ValueError("Bad close for {}".format(ticker))
        rows[ticker] = {
            "valuation_date": day,
            "universe_ticker": ticker,
            "currency": "USD",
            "close_price": str(close),
            "price_basis": "unadjusted",
            "source_system": "massive",
            "provider_request_id": response.get("request_id") or "",
        }
    return rows


def saved_file(folder, day):
    price_file = folder / "prices.csv"
    manifest_file = folder / "manifest.json"
    response_file = folder / "response.json"
    if not folder.exists():
        return None
    if not price_file.is_file() or not manifest_file.is_file() or not response_file.is_file():
        raise ValueError("Incomplete Massive delivery in {}".format(folder))
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    digest = hashlib.sha256(price_file.read_bytes()).hexdigest()
    response_digest = hashlib.sha256(response_file.read_bytes()).hexdigest()
    if (manifest.get("business_date") != day or manifest.get("sha256") != digest
            or manifest.get("response_sha256") != response_digest):
        raise ValueError("Saved Massive delivery changed: {}".format(folder))
    return price_file


def fetch(day, data_dir=Path("data")):
    day = date.fromisoformat(day).isoformat()
    folder = data_dir / "provider_prices" / "massive" / day
    existing = saved_file(folder, day)
    if existing:
        print("Using saved Massive delivery for {}".format(day))
        return existing

    api_key = read_api_key()
    response = get_response(day, api_key)
    rows = price_rows(day, response)

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for ticker in sorted(rows):
        writer.writerow(rows[ticker])
    contents = output.getvalue().encode("utf-8")
    digest = hashlib.sha256(contents).hexdigest()
    response_bytes = (json.dumps(response, sort_keys=True, separators=(",", ":"))
                      + "\n").encode("utf-8")
    manifest = {
        "business_date": day,
        "source_system": "massive",
        "endpoint": BASE_URL + day,
        "adjusted": False,
        "request_id": response.get("request_id"),
        "record_count": len(rows),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sha256": digest,
        "response_sha256": hashlib.sha256(response_bytes).hexdigest(),
    }
    folder.mkdir(parents=True)
    (folder / "prices.csv").write_bytes(contents)
    (folder / "response.json").write_bytes(response_bytes)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                          encoding="utf-8")
    print("Saved {} Massive closes for {}".format(len(rows), day))
    return folder / "prices.csv"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    try:
        file_path = fetch(args.business_date, args.data_dir)
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, "Price fetch stopped: {}\n".format(error))
    print(file_path)


if __name__ == "__main__":
    main()
