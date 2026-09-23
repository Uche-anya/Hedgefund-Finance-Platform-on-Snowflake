# Merger history review

Reviewed September 22, 2026. These decisions concern price history identity;
they do not implement corporate-action accounting for holdings.

## EXE: check CHK continuity

Chesapeake completed its Southwestern combination on October 1, 2024 and
renamed itself Expand Energy. CHK traded through October 1; EXE began October 2.
The candidate earlier history is CHK. Do not append SWN prices: Southwestern
shareholders received shares under the merger's exchange terms.

[Issuer closing announcement](https://investors.expandenergy.com/news-releases/news-release-details/chesapeake-energy-and-southwestern-energy-complete-merger-and)

Before downloading earlier prices, compare Massive's CHK October 1 and EXE
October 2 records, including share-class FIGI, issuer, currency and exchange.
Matching issuer names alone is insufficient.

## VMRK: check EQR continuity

The August 17, 2026 closing filing identifies Vivmark as formerly Equity
Residential. AvalonBay holders received 2.793 company common shares per AVB
share, with cash for fractional shares, subject to the stated exclusions.
The candidate earlier price history is EQR, not AVB. An AVB holding would
require a share conversion event instead of merely changing its ticker.

[Closing 8-K, introductory note and Item 2.01](https://www.sec.gov/Archives/edgar/data/906107/000114036126033377/ef20080318_8k.htm)

Compare EQR on August 17 with VMRK on August 18 before approving a price repair.
Provider security type may reflect a REIT; inspect it rather than assuming CS.

## PSKY: retain its separate history

The Skydance transaction involved a new issuer and newly issued shares.
Old Paramount Class B holders could receive new Class B shares or elect cash,
subject to the transaction's proration rules. Class A had different terms.
Treating PARA to PSKY as a simple rename would hide these differences.

[Closing 8-K12B](https://www.sec.gov/Archives/edgar/data/2041610/000119312525175046/d841914d8k12b.htm)

Keep PSKY's observed August 7, 2025 start. Save PARA August 6 and PSKY August 7
reference records as evidence, but do not concatenate their prices. A future
scenario holding PARA across the transaction needs explicit consideration and
election handling. Matching provider identifiers would not override that rule.

## Next local check

Run `python -m data_extraction.check_merger_identities` and enter the key at the hidden prompt.
Six requests take about 65 seconds plus network time. The script reuses the
reference downloader, preserving the raw responses, identities.csv and a
manifest in a new data/reference_checks folder. It does not download prices.

The six live checks completed in reference snapshot
db78b7c287e646b8867efab11d4a6555. CHK/EXE share-class and composite FIGIs match;
EXE's CIK is missing. EQR/VMRK match on both FIGIs and CIK. PARA/PSKY differ
on all three identifiers, supporting their separate treatment.

## Repair the two continuing histories

Run `python -m data_extraction.repair_merger_histories`. It checks the saved reference file
fingerprints and expected identifiers, then downloads CHK through October 1,
2024 and EQR through August 17, 2026. It combines those with the saved EXE and
VMRK prices from the following trading day onward. The missing EXE CIK is a
specific documented exception supported by matching FIGIs and the issuer
announcement; the raw missing value is preserved. Other missing identifiers
or conflicts stop the repair.

The new data/price_repairs folder contains EXE_prices.csv, VMRK_prices.csv,
raw inputs, identity decisions and a manifest written only after both succeed.
Rows retain source tickers and stable instrument IDs. Coverage is checked
against AAPL dates, not an independent exchange calendar. Original files and
PSKY prices stay unchanged. No Snowflake load or holding conversion occurs.
An interrupted batch has no completion manifest; rerunning starts a new folder.

Status: both live repairs completed in a3d7d54cebdc41d6a5d700d67fa72f84,
with 500 rows each and dates matching AAPL. They are included by the
[assembly script](assembled_prices.md).
