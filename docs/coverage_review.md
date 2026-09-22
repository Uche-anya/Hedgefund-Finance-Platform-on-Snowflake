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

Four symbol changes (ECHO, P, FISV, MRSH) are candidates for retrieving earlier
history. First query Massive's dated identities before and after each change.
Compare share-class identifiers and issuer identities. FISV also moved exchange,
so an exchange mismatch is expected and documented, not automatically a failure.

For FDXF, HONA, Q and SNDK, retain the shorter regular-way history as the intended
scope. Regular-way means ordinary trading after the listing/separation. Some
have earlier when-issued markets (trading ahead of delivery); do not silently
mix those into this dataset. Confirm the provider's security identity before
using any of these in valuations. Do not backfill using the parent stock.

EXE, PSKY and VMRK need merger-specific review. Identify the surviving security,
share classes, consideration and conversion ratios before joining histories.
Do not simply combine two predecessor price series. Until reviewed, keep the
downloaded post-event series separate and exclude unsupported earlier scenarios.

These findings explain the observed starting dates; they do not certify all
rows, all calendar sessions or every security in the 503-ticker universe.
Parent securities can also require split/distribution handling despite having
500 rows. HON is an explicit example in the exchange notice.

No new price repairs or provider identity requests were run in this step.
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
