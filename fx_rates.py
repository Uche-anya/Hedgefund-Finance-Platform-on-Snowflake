"""Preserve ECB EUR-based reference rates and derive dated GBP-per-USD rates."""

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import hashlib
import io
import json
from pathlib import Path
from uuid import uuid4

from market_prices import DATES, fetch


URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D.USD+GBP.EUR.SP00.A"
       f"?startPeriod={DATES[0]}&endPeriod={DATES[-1]}&format=csvdata")
SOURCE = "Source: ECB statistics. GBP-per-USD cross rate calculated by this project."
POLICY = "https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html"
COLUMNS = ["valuation_date", "from_currency", "to_currency", "usd_per_eur", "gbp_per_eur", "gbp_per_usd"]
FILES = ("ecb_rates.csv", "usd_gbp.csv")


def normalize(payload):
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")))
    required = {"TIME_PERIOD", "OBS_VALUE", "CURRENCY", "CURRENCY_DENOM", "FREQ", "EXR_TYPE", "EXR_SUFFIX", "UNIT_MULT"}
    if not reader.fieldnames or not required <= set(reader.fieldnames) or len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValueError("ECB response is missing required columns or has duplicate columns")
    rates = {}
    for row in reader:
        if None in row or any(row.get(field) is None for field in required):
            raise ValueError("Malformed ECB row")
        if any(row[field] != expected for field, expected in {
            "CURRENCY_DENOM": "EUR", "FREQ": "D", "EXR_TYPE": "SP00", "EXR_SUFFIX": "A", "UNIT_MULT": "0"
        }.items()):
            raise ValueError("Unexpected ECB base currency, frequency, rate type or units")
        day, currency = row["TIME_PERIOD"], row["CURRENCY"]
        if day not in DATES or currency not in ("USD", "GBP"):
            raise ValueError("Unexpected ECB date or currency")
        key = (day, currency)
        if key in rates:
            raise ValueError(f"Duplicate ECB observation: {key}")
        try:
            rate = Decimal(row["OBS_VALUE"])
        except InvalidOperation as error:
            raise ValueError("Invalid ECB rate") from error
        if not rate.is_finite() or rate <= 0:
            raise ValueError("ECB rate must be finite and positive")
        rates[key] = rate
    if set(rates) != {(day, currency) for day in DATES for currency in ("USD", "GBP")}:
        raise ValueError("Missing required ECB rate/date; no stale-rate fallback")
    rows = []
    with localcontext() as context:
        context.prec = 40
        for day in DATES:
            usd, gbp = rates[(day, "USD")], rates[(day, "GBP")]
            cross = (gbp / usd).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP)
            if cross <= 0:
                raise ValueError("Cross rate is too small for the selected precision")
            rows.append(dict(zip(COLUMNS, [day, "USD", "GBP", str(usd), str(gbp), str(cross)])))
    return rows


def csv_bytes(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def download_fx(root):
    folder = root / uuid4().hex
    folder.mkdir(parents=True, exist_ok=False)
    try:
        payload = fetch(URL)
        (folder / "ecb_rates.csv").write_bytes(payload)
        if len(payload) > 2_000_000:
            raise ValueError("Oversized ECB response")
        rows = normalize(payload)
        (folder / "usd_gbp.csv").write_bytes(csv_bytes(rows))
        manifest = {
            "schema_version": 1, "source": SOURCE, "url": URL, "usage_policy": POLICY,
            "received_at_utc": datetime.now(timezone.utc).isoformat(), "dates": list(DATES),
            "from_currency": "USD", "to_currency": "GBP", "rate_unit": "GBP per USD",
            "formula": "GBP per EUR / USD per EUR", "rate_decimal_places": 12,
            "rounding": "ROUND_HALF_UP", "row_count": len(rows),
            "sha256": {name: hashlib.sha256((folder / name).read_bytes()).hexdigest() for name in FILES},
        }
        temporary = folder / "manifest.json.tmp"
        temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary.rename(folder / "manifest.json")
    except Exception as error:
        (folder / "failure.json").write_text(json.dumps({"url": URL, "error": str(error)}), encoding="utf-8")
        raise RuntimeError(f"Incomplete FX delivery; diagnostics preserved in {folder}") from error
    return folder


def verify_fx(folder):
    if not (folder / "manifest.json").is_file():
        raise ValueError("Incomplete FX delivery: manifest missing")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    expected = {"schema_version": 1, "dates": list(DATES), "from_currency": "USD", "to_currency": "GBP",
                "rate_unit": "GBP per USD", "formula": "GBP per EUR / USD per EUR",
                "rate_decimal_places": 12, "rounding": "ROUND_HALF_UP", "row_count": 3}
    if any(manifest.get(key) != value for key, value in expected.items()) or set(manifest.get("sha256", {})) != set(FILES):
        raise ValueError("Unexpected FX direction or delivery contract")
    for name in FILES:
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != manifest["sha256"][name]:
            raise ValueError(f"Changed FX file: {name}")
    rows = normalize((folder / "ecb_rates.csv").read_bytes())
    if csv_bytes(rows) != (folder / "usd_gbp.csv").read_bytes():
        raise ValueError("Derived FX rates do not match original ECB observations")
    return {row["valuation_date"]: row for row in rows}


if __name__ == "__main__":
    print(download_fx(Path(__file__).resolve().parent / "data" / "fx"))
