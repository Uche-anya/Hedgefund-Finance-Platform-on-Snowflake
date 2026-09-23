# Review of the 11 remaining short histories

Reviewed September 22, 2026 against issuer announcements, exchange notices and
filings. See [coverage_review.csv](../config/coverage_review.csv) for dated
classifications, sources and proposed actions. These are research decisions,
not approved machine-readable security mappings. No price data was changed.

## Findings

| Ticker | Observed start | Finding | Next action |
| --- | --- | --- | --- |
| ECHO | 2026-06-24 | ticker change | verify then backfill |
| P | 2026-04-17 | ticker change | verify then backfill |
| EXE | 2024-10-02 | merger and rename | review merger before backfill |
| FDXF | 2026-06-01 | spinoff | retain regular way start |
| FISV | 2025-11-11 | ticker and exchange change | verify then backfill |
| HONA | 2026-06-29 | spinoff | retain regular way start |
| MRSH | 2026-01-14 | ticker change | verify then backfill |
| PSKY | 2025-08-07 | merger new listing | review merger before backfill |
| Q | 2025-11-03 | spinoff | retain regular way start |
| SNDK | 2025-02-24 | spinoff | retain regular way start |
| VMRK | 2026-08-18 | merger and rename | review merger before backfill |

## How to apply this review

Run `python -m data_extraction.check_ticker_changes` to collect all eight dated reference
responses for SATS/ECHO, PSTG/P, FI/FISV and MMC/MRSH. Enter the Massive key at
the hidden prompt. Seven 13-second pauses mean roughly 90 seconds plus network
time. It reuses the existing reference downloader and saves identities.csv,
raw JSON evidence and comparisons.csv in a new data/reference_checks folder.

IDENTIFIERS_MATCH means both observed identifiers and the expected security
details agree. REVIEW_MISSING or REVIEW_CONFLICT requires investigation. Missing
identifiers do not count as matches. Fiserv's expected NYSE-to-Nasdaq move is
explicitly allowed. Names are included for human review, since rebranding can
change them. No result automatically authorizes a price merge or proves daily
identity continuity throughout the full historical period.

The live batch check completed in reference snapshot
cfbd21edcf604c449200a1dc472ee1d5. ECHO, P and MRSH matched all checked fields.
FISV matched share-class and composite FIGIs but lacked the new CIK.

## Fiserv exception and batch repair

The Fiserv exception was reviewed against [Nasdaq notice DTN2025-32](https://nasdaqtrader.com/TraderNews.aspx?id=DTN2025-32).
The notice maps FI on NYSE to FISV on Nasdaq on November 11, 2025 and gives the
same CUSIP (337738108) on both sides. Saved Massive responses have the same
share-class FIGI BBG001S5R6Q4 and composite FIGI BBG000BJKPG0. The earlier CIK is
0000798354; the missing later CIK is retained as missing, not filled in.

`python -m data_extraction.repair_ticker_changes` verifies the saved evidence and applies only
this specific missing-CIK exception. Other missing fields or conflicting values
still fail. It downloads SATS, PSTG, FI and MMC up to the respective change,
then combines them with the new-symbol rows on or after the change date.

The output is a new data/price_repairs folder with ECHO_prices.csv, P_prices.csv,
FISV_prices.csv and MRSH_prices.csv. Each row retains the source ticker and
a stable internal instrument ID. Inputs, identity decisions and fingerprints
are preserved. The batch manifest is written only after all four repairs pass.
If interrupted, the folder is incomplete; rerunning starts a new batch.

Coverage checks compare against saved AAPL dates, not an independently verified
exchange calendar. Original data and the earlier repairs are unchanged. Four
requests take about 40 seconds plus network time; no Snowflake load happens.
Status: the user reported all four live repairs completed with 500 rows each
and dates matching AAPL in data/price_repairs/0f1d760ceb80466eb129665af599dd2d.

Four symbol changes (ECHO, P, FISV, MRSH) are candidates for retrieving earlier
history. First query Massive's dated identities before and after each change.
Compare share-class identifiers and issuer identities. FISV also moved exchange,
so an exchange mismatch is expected and documented, not automatically a failure.

For FDXF, HONA, Q and SNDK, retain the shorter regular-way history as the intended
scope. Regular-way means ordinary trading after the listing/separation. Some
have earlier when-issued markets (trading ahead of delivery); do not silently
mix those into this dataset. Confirm the provider's security identity before
using any of these in valuations. Do not backfill using the parent stock.

The [merger review](merger_review.md) identifies CHK/EXE and EQR/VMRK as
continuity candidates requiring dated provider checks. PSKY keeps its separate
post-merger history. Run `python -m data_extraction.check_merger_identities` for all six records.
Until the continuity checks are reviewed, keep these downloaded series separate
and exclude unsupported earlier scenarios.

These findings explain the observed starting dates; they do not certify all
rows, all calendar sessions or every security in the 503-ticker universe.
Parent securities can also require split/distribution handling despite having
500 rows. HON is an explicit example in the exchange notice.

The original research step did not download price repairs. The subsequent
identity checks and repair readiness are recorded above.
BNY and XYZ's previously saved repairs remain separate from the main snapshot.

## Evidence

- **ECHO:** Same stock symbol change; company says CUSIP unchanged. [Primary source](https://www.miaxglobal.com/alert/2026/06/23/miax-exchange-group-options-markets-corporate-action-alert-echostar-0).
- **P:** Everpure announced symbol change; CUSIP unchanged. [Primary source](https://www.everpuredata.com/uk/company/newsroom/press-releases/everpure-to-change-ticker-symbol.html).
- **EXE:** CHK became EXE after Southwestern combination; investigate CHK continuity and SWN conversion separately. [Primary source](https://investors.expandenergy.com/news-releases/news-release-details/chesapeake-energy-and-southwestern-energy-complete-merger-and).
- **FDXF:** New FedEx Freight security; never substitute parent FDX prices. Earlier when-issued market is outside current scope. [Primary source](https://investor.fedex.com/news-and-events/investor-news/investor-news-details/2026/FedEx-Completes-Spin-Off-of-FedEx-Freight/default.aspx).
- **FISV:** NYSE FI moved to Nasdaq FISV; same CUSIP per Nasdaq. Expected exchange difference must be allowed. [Primary source](https://nasdaqtrader.com/TraderNews.aspx?id=DTN2025-32).
- **HONA:** Separate Honeywell Aerospace shares; do not attach HON prices. HONAV when-issued trading predates regular-way start; HON also reverse-split. [Primary source](https://www.nasdaqtrader.com/TraderNews.aspx?id=ECA2026-399).
- **MRSH:** Marsh symbol and brand change; issuer says CUSIP unchanged. [Primary source](https://www.marsh.com/en/corp/about/news/marsh-mclennan-to-change-nyse-symbol-to-mrsh.html).
- **PSKY:** New Paramount Class B listing after Skydance transaction; do not mechanically splice PARA prices or share classes. [Primary source](https://www.paramount.com/press/skydance-media-and-paramount-global-complete-merger-creating-next-generation-media-company).
- **Q:** Qnity separated November 1 and regular-way trading started November 3; do not substitute DD history. [Primary source](https://www.dupont.com/news/dupont-completes-separation-of-qnity-electronics.html).
- **SNDK:** Separate Sandisk listing after Western Digital separation; do not substitute WDC prices. [Primary source](https://investor.sandisk.com/node/6606/pdf).
- **VMRK:** EQR renamed after AvalonBay merger; review EQR continuity separately from AVB conversion at 2.793 shares. [Primary source](https://investors.vivmarkresidential.com/news-events/press-releases/detail/113/vivmark-residential-launches-as-one-of-the-countrys-leading-real-estate-companies).
