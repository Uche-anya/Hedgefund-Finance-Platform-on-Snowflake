# Historical prices: 503 tickers

The two-stock live check passed: 250 daily bars each for Apple and Amazon in 2025.
The full download completed: 503 tickers and 247,958 rows. Inspection found 490
tickers with 500 rows and 13 shorter histories. Separate BNY and Block repairs
now contain 500 rows each. See coverage_review.md for the other 11 cases.

## Universe

config/stock_universe.csv contains 503 unique tickers across 11 sectors.
The community-maintained list comes from:
https://github.com/datasets/s-and-p-500-companies

config/stock_universe_source.json records its source, download time and fingerprint.
This is our frozen project universe, not an official or historical index-membership
feed. Multiple share classes explain why the list has more than 500 tickers.
It has survivorship bias: past companies absent from this list are excluded.
New listings and ticker changes can also have shorter price histories.

## Run

Run: python -m data_extraction.historical_prices

Paste your key at the hidden prompt. It is not stored. MASSIVE_API_KEY can also
supply the key through the environment.

The range runs from one day inside the two-year anniversary through yesterday,
using New York's date. Starting September 22, 2026 requests September 23, 2024
through September 21, 2026. The day of margin avoids the free-plan boundary.
Dates are frozen in request.json when the run starts.

Expect roughly 250,000 rows if most tickers have full coverage; actual counts
come from the responses. 503 requests with 13-second spacing take about 109
minutes plus network time. Other activity on your key shares the rate limit.

## Resume

The program prints the exact resume command at startup:
python -m data_extraction.historical_prices --resume "data/historical_prices/YOUR_FOLDER_ID"

Use it after Ctrl+C or a network failure. Completed files are validated and their
fingerprints checked before being skipped. Only unfinished tickers are fetched.
Wait a minute after rate-limit errors. Avoid concurrent runs against one folder.

Invalid or empty responses stop the run for investigation, without silently
removing tickers. Missing bars are not invented or forward-filled. A long-delayed
resume may lose access to the earliest dates as the free access window moves.
The earlier two-stock snapshot lacks request/progress files and is not resumable
with this new mechanism. Running without --resume starts a fresh snapshot.

## Snapshot contents

- Original JSON responses, one per ticker.
- stock_universe.csv: copy of the input list.
- request.json: frozen symbols and dates.
- progress.json: completed counts, receipt times and file fingerprints.
- manifest.json: written only after all requested tickers pass validation.

Prices remain under Git-ignored data/. Ticker configuration is tracked separately.

## Fields and limitations

Each daily bar contains open (o), high (h), low (l), close (c), volume (v), and
start timestamp (t). Dates are interpreted in America/New_York. We request and
verify adjusted=false: prices are not split-adjusted. Splits, dividends and
instrument identity changes need separate handling in historical calculations.

These are provider aggregates, not certified official closing-auction prices.
Validation does not yet confirm every expected exchange session is present.
This step saves raw history. Normalization and Snowflake loading come later.
The earlier EODHD sample and existing Snowflake models remain separate.

References:
https://massive.com/pricing
https://massive.com/docs/rest/quickstart
https://massive.com/docs/rest/stocks/aggregates/custom-bars
