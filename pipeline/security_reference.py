"""Save Massive ticker details for a dated security review."""

import argparse
import csv
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from pipeline.massive_prices import read_api_key


URL = "https://api.massive.com/v3/reference/tickers/"


def get_ticker(ticker, as_of, key):
    url = URL + quote(ticker, safe="") + "?" + urlencode({"date": as_of})
    request = Request(url, headers={"Authorization": "Bearer " + key,
                                    "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ValueError("Ticker response is unexpectedly large")
            data = json.loads(body)
            if data.get("status") != "OK" or not isinstance(data.get("results"), dict):
                raise ValueError("Invalid ticker response for {}".format(ticker))
            if data["results"].get("ticker") != ticker:
                raise ValueError("Ticker response changed symbol for {}".format(ticker))
            return data
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError("Massive returned HTTP {} for {}".format(error.code, ticker)) from None
        except URLError:
            if attempt == 2:
                raise RuntimeError("Could not reach Massive for {}".format(ticker)) from None
        time.sleep(2 * (attempt + 1))


def save_review(as_of, tickers, data_dir=Path("data")):
    as_of = date.fromisoformat(as_of).isoformat()
    tickers = list(dict.fromkeys(tickers))
    if not tickers or any(not ticker.isascii() or not ticker.replace(".", "").isalnum()
                          for ticker in tickers):
        raise ValueError("Give one or more US ticker symbols")

    key = read_api_key()
    responses = {ticker: get_ticker(ticker, as_of, key) for ticker in tickers}
    folder = data_dir / "security_reference" / as_of / uuid4().hex
    folder.mkdir(parents=True)
    rows = []
    for ticker, response in responses.items():
        (folder / (ticker + ".json")).write_text(json.dumps(response, indent=2) + "\n",
                                                  encoding="utf-8")
        details = response["results"]
        rows.append({"as_of": as_of, "ticker": ticker, "name": details.get("name"),
                     "active": details.get("active"), "market": details.get("market"),
                     "type": details.get("type"), "currency": details.get("currency_name"),
                     "cik": details.get("cik"), "share_class_figi": details.get("share_class_figi"),
                     "request_id": response.get("request_id")})

    with (folder / "identities.csv").open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (folder / "manifest.json").write_text(json.dumps({
        "as_of": as_of, "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "tickers": tickers, "source": URL,
    }, indent=2) + "\n", encoding="utf-8")
    return folder, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("as_of", help="Date to inspect, YYYY-MM-DD")
    parser.add_argument("tickers", nargs="+", help="Provider tickers to inspect")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    try:
        folder, rows = save_review(args.as_of, args.tickers, args.data_dir)
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, "Security reference stopped: {}\n".format(error))
    for row in rows:
        print("{}: {} | CIK {} | FIGI {}".format(
            row["ticker"], row["name"], row["cik"], row["share_class_figi"]))
    print("Review evidence: {}".format(folder))


if __name__ == "__main__":
    main()
