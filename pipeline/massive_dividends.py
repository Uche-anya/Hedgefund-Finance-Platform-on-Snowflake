"""Save a dated snapshot of Massive dividend announcements."""

import argparse
import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from pipeline.massive_prices import read_api_key


URL = "https://api.massive.com/stocks/v1/dividends"


def request_page(url, key):
    address = urlparse(url)
    if address.scheme != "https" or address.netloc != "api.massive.com":
        raise ValueError("Unexpected Massive pagination URL")
    if address.path != "/stocks/v1/dividends":
        raise ValueError("Unexpected Massive pagination path")
    request = Request(url, headers={"Authorization": "Bearer " + key,
                                    "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read(10_000_001)
            if len(body) > 10_000_000:
                raise ValueError("Massive dividend page is unexpectedly large")
            return json.loads(body)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError("Massive returned HTTP {}".format(error.code)) from None
        except URLError:
            if attempt == 2:
                raise RuntimeError("Could not reach Massive") from None
        time.sleep(2 * (attempt + 1))


def get_pages(start, end, key):
    query = urlencode({"ex_dividend_date.gte": start,
                       "ex_dividend_date.lte": end,
                       "limit": 5000,
                       "sort": "ex_dividend_date.asc"})
    url = URL + "?" + query
    pages = []
    seen_urls = set()
    while url:
        if url in seen_urls or len(pages) == 20:
            raise ValueError("Massive dividend pagination did not finish")
        seen_urls.add(url)
        page = request_page(url, key)
        if page.get("status") != "OK" or not isinstance(page.get("results"), list):
            raise ValueError("Massive returned an invalid dividend page")
        pages.append(page)
        url = page.get("next_url")
    return pages


def records_from_pages(pages, start, end):
    records = {}
    for page in pages:
        for event in page["results"]:
            if not isinstance(event, dict):
                raise ValueError("Invalid dividend record")
            ex_date = event.get("ex_dividend_date")
            if not ex_date or not start <= ex_date <= end:
                raise ValueError("Dividend has an ex-date outside the requested window")
            event_id = event.get("id")
            if not event_id or not event.get("ticker"):
                raise ValueError("Dividend lacks an event ID or ticker")
            if event_id in records and records[event_id] != event:
                raise ValueError("Conflicting dividend records for {}".format(event_id))
            records[event_id] = event
    return records


def save_snapshot(day, pages, data_dir=Path("data"), lookback=30, lookahead=45):
    day = date.fromisoformat(day).isoformat()
    start = (date.fromisoformat(day) - timedelta(days=lookback)).isoformat()
    end = (date.fromisoformat(day) + timedelta(days=lookahead)).isoformat()
    records = records_from_pages(pages, start, end)
    lines = [json.dumps(records[event_id], sort_keys=True, separators=(",", ":")) + "\n"
             for event_id in sorted(records)]
    body = "".join(lines).encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    delivery_id = "massive-dividends-{}-{}".format(day.replace("-", ""), digest[:16])
    folder = data_dir / "provider_dividends" / day / delivery_id
    if folder.exists():
        if hashlib.sha256((folder / "dividends.jsonl").read_bytes()).hexdigest() != digest:
            raise ValueError("Saved dividend delivery changed: {}".format(folder))
        saved = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        response_hash = hashlib.sha256((folder / "response_pages.json").read_bytes()).hexdigest()
        if saved["response_sha256"] != response_hash:
            raise ValueError("Saved provider response changed: {}".format(folder))
        return folder

    folder.mkdir(parents=True)
    (folder / "dividends.jsonl").write_bytes(body)
    evidence = json.dumps(pages, sort_keys=True, separators=(",", ":")) + "\n"
    (folder / "response_pages.json").write_bytes(evidence.encode("utf-8"))
    manifest = {
        "business_date": day,
        "delivery_id": delivery_id,
        "source_system": "massive",
        "ex_date_from": start,
        "ex_date_to": end,
        "record_count": len(records),
        "page_count": len(pages),
        "records_sha256": digest,
        "response_sha256": hashlib.sha256(evidence.encode("utf-8")).hexdigest(),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                          encoding="utf-8")
    return folder


def fetch(day, data_dir=Path("data"), lookback=30, lookahead=45):
    day = date.fromisoformat(day).isoformat()
    start = (date.fromisoformat(day) - timedelta(days=lookback)).isoformat()
    end = (date.fromisoformat(day) + timedelta(days=lookahead)).isoformat()
    pages = get_pages(start, end, read_api_key())
    return save_snapshot(day, pages, data_dir, lookback, lookahead)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date", help="US market date, YYYY-MM-DD")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    try:
        folder = fetch(args.business_date, args.data_dir)
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as error:
        parser.exit(1, "Dividend fetch stopped: {}\n".format(error))
    print("Saved {} dividends from {} pages: {}".format(
        manifest["record_count"], manifest["page_count"], folder))


if __name__ == "__main__":
    main()
