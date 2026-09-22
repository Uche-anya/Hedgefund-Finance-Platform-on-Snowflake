# Investigate BK and BNY before joining their prices

Run `python check_bny_identity.py` and paste the Massive key at its hidden prompt.
Four reference requests are spaced 13 seconds apart. The check takes roughly
40 seconds plus network time. Raw responses, identities.csv and a manifest are
saved under data/reference_checks in a new folder. No price file is modified.

The queries are BNY and BK on February 6, 2026, BK on May 20, and BNY on May 21.
We want evidence for these expectations, not assumptions baked into the code:

- The February BNY record identifies the BlackRock municipal fund.
- BK on both dates identifies Bank of New York Mellon.
- The May BNY record identifies the bank, with identifiers consistent with BK.

CIK identifies the SEC registrant, not a particular share class. A matching CIK
alone is insufficient: compare share-class FIGI, composite FIGI, security type,
exchange, currency and name too. Missing identifiers are inconclusive, not matches.
Conflicting identifiers require review. These four dates do not by themselves
prove instrument continuity across every day of the two-year history.

Official announcements supporting the investigation:
- https://www.bny.com/corporate/global/en/about-us/newsroom/press-release/bny-announces-planned-change-of-stock-ticker-symbol-to-bny-130465.html
- https://www.blackrock.com/us/individual/literature/press-release/1-2-26-pr-muni-div-release.pdf

API reference:
https://massive.com/docs/rest/stocks/tickers/ticker-overview

The live reference check returned the bank share-class FIGI BBG001S5P6Q6 for
both BK dates and BNY on May 21. Their composite FIGI, common-stock type,
exchange and currency also agree. The earlier BNY fund has a different FIGI.
The missing CIK on May 21 remains missing; it is not fabricated.

## Build the separate bank history

Run `python repair_bny_history.py` and enter the API key at the hidden prompt.
The defaults point to our completed price and reference snapshots. Optional
--snapshot and --references arguments accept other matching snapshot folders.

The script verifies the saved evidence fingerprints and identity fields,
requests BK from the original start date through May 20, 2026, then combines
those bars with BNY from May 21 onward. Pre-change BNY fund bars are excluded.
All output goes to a new data/price_repairs folder; source files stay intact.

bank_prices.csv records a stable internal ID (US_BNY_MELLON_COMMON), the bank
share-class FIGI, original ticker, date, currency, unadjusted OHLC and volume.
The repair folder also preserves the raw inputs and reference evidence. A
manifest is written only after validation succeeds.

Coverage must match the saved AAPL dates, with no duplicate bank dates. This is
a peer comparison, not independent exchange-calendar verification. The four
reference observations do not establish daily identifier coverage for the
entire period. Other ticker changes in the universe still need investigation.

Status: the live BK download and repair completed with 500 rows, with no duplicate
dates or gaps against saved AAPL dates. Output is in
data/price_repairs/f978b4aac9584f1da97870318dcc6b98/bank_prices.csv.
The original universe snapshot and Snowflake models do not automatically use
the repair; integration follows review of the new output.

## Block repair

`python check_xyz_identity.py` confirmed matching CIK and share-class FIGI for
SQ on January 17, 2025 and XYZ on January 21, 2025. Run
`python repair_xyz_history.py` to create a separate Block history using SQ before
January 21 and XYZ from that date. It uses the same preservation and coverage
checks described above and writes block_prices.csv.

The live run completed with 500 rows in
data/price_repairs/e391cf0dcbf142978deacc40d77211ba/block_prices.csv.
Both repairs retain source tickers alongside stable internal instrument IDs.
