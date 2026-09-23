"""Download a deliberately small EODHD demo dataset; keep raw responses for replay."""

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4


SYMBOLS = ("AAPL.US", "AMZN.US")
DATES = ("2025-01-06", "2025-01-07", "2025-01-08")
FILES = tuple(f"{symbol}.json" for symbol in SYMBOLS) + ("closing_prices.csv",)
DOCS = "https://eodhd.com/financial-apis/api-for-historical-data-and-volumes"
TERMS = "https://eodhd.com/financial-apis/terms-conditions"


def fetch(url):
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "NorthbridgeLocalLearning/1.0"})
            with urlopen(request, timeout=15) as response:
                return response.read(2_000_001)
        except HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise
            if attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)


def normalize(payload, symbol):
    if symbol not in SYMBOLS or len(payload) > 2_000_000:
        raise ValueError("Unsupported symbol or oversized response")
    records = json.loads(payload, parse_float=Decimal)
    if not isinstance(records, list) or not records:
        raise ValueError(f"{symbol}: expected a nonempty daily-price array, not an API error")
    prices = {}
    for row in records:
        if not isinstance(row, dict) or not {"date", "open", "high", "low", "close", "volume"} <= row.keys():
            raise ValueError(f"{symbol}: missing expected daily-price fields")
        day = row["date"]
        if day not in DATES or day in prices:
            raise ValueError(f"{symbol}: duplicate or unexpected date {day}")
        try:
            values = {key: Decimal(str(row[key])) for key in ("open", "high", "low", "close", "volume")}
        except InvalidOperation as error:
            raise ValueError(f"{symbol}: invalid numeric value") from error
        if any(not value.is_finite() for value in values.values()):
            raise ValueError(f"{symbol}: non-finite value")
        if any(values[key] <= 0 for key in ("open", "high", "low", "close")):
            raise ValueError(f"{symbol}: nonpositive price")
        if not (values["low"] <= values["open"] <= values["high"] and
                values["low"] <= values["close"] <= values["high"]):
            raise ValueError(f"{symbol}: inconsistent daily price range")
        if values["volume"] < 0 or values["volume"] != values["volume"].to_integral_value():
            raise ValueError(f"{symbol}: invalid volume")
        prices[day] = values["close"]
    if set(prices) != set(DATES):
        raise ValueError(f"{symbol}: missing required trading dates")
    return [{"valuation_date": day, "instrument": symbol, "currency": "USD",
             "close_price": str(prices[day])} for day in DATES]


def price_csv(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["valuation_date", "instrument", "currency", "close_price"])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def download(root):
    folder = root / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    requests = []
    rows = []
    try:
        for symbol in SYMBOLS:
            # This is the provider's PUBLIC demo token, not a personal credential.
            query = urlencode({"api_token": "demo", "from": DATES[0], "to": DATES[-1],
                               "period": "d", "order": "a", "fmt": "json"})
            url = f"https://eodhd.com/api/eod/{symbol}?{query}"
            payload = fetch(url)
            (folder / f"{symbol}.json").write_bytes(payload)
            requests.append({"symbol": symbol, "url": url, "received_at_utc": datetime.now(timezone.utc).isoformat()})
            rows.extend(normalize(payload, symbol))
        (folder / "closing_prices.csv").write_bytes(price_csv(rows))
        manifest = {"schema_version": 1, "source": "EODHD demo API", "currency": "USD",
                    "price_field": "close", "price_basis": "unadjusted", "dates": DATES,
                    "symbols": SYMBOLS, "row_count": len(rows), "requests": requests,
                    "documentation": DOCS, "terms": TERMS,
                    "usage": "private learning only; redistribution not authorised",
                    "sha256": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in FILES}}
        temporary = folder / "manifest.json.tmp"
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary.rename(folder / "manifest.json")
    except Exception as error:
        (folder / "failure.json").write_text(json.dumps({"error": str(error), "completed_requests": requests}, indent=2), encoding="utf-8")
        raise RuntimeError(f"Market download incomplete; diagnostics preserved in {folder}") from error
    return folder


def verify_market(folder):
    path = folder / "manifest.json"
    if not path.is_file():
        raise ValueError("Incomplete market delivery: manifest missing")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != 1 or manifest.get("currency") != "USD" or
            manifest.get("symbols") != list(SYMBOLS) or manifest.get("dates") != list(DATES) or
            manifest.get("price_field") != "close" or manifest.get("price_basis") != "unadjusted" or
            manifest.get("row_count") != 6 or set(manifest.get("sha256", {})) != set(FILES)):
        raise ValueError("Unexpected market delivery contract")
    for name in FILES:
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != manifest["sha256"][name]:
            raise ValueError(f"Changed market file: {name}")
    rows = [row for symbol in SYMBOLS for row in normalize((folder / f"{symbol}.json").read_bytes(), symbol)]
    if (folder / "closing_prices.csv").read_bytes() != price_csv(rows):
        raise ValueError("Normalised prices do not match preserved raw responses")
    return rows


if __name__ == "__main__":
    print(download(Path(__file__).resolve().parents[1] / "data" / "market"))
