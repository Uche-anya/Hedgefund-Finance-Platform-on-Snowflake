# Part 8: real historical prices, simulated trading activity

We now download historical observations for two real securities: Apple
(`AAPL.US`) and Amazon (`AMZN.US`). We keep our invented ALPHA/BETA fixtures
unchanged so their hand-worked tests remain predictable.

## Source and permitted scope

We selected the **EODHD public demo API** for this private learning exercise.
Its documentation lists both symbols as available with its public `demo` token,
without opening an account. We request 6, 7 and 8 January 2025. This is a small
historical replay, not a current market feed.

The provider describes `close` as unadjusted; `adjusted_close` includes split
and dividend adjustments. We select `close` and preserve the entire response.
The provider also describes its prices as indicative, so this exercise does
not establish a licensed, official-exchange production valuation source.

The terms permit private storage and analysis but restrict redistribution and
commercial use. Downloaded prices, the hybrid example and derived reports stay
under Git-ignored `data/`. Do not put them into a public repository or public
dashboard without appropriate permission. Committed API test responses are
invented data, not copied vendor observations.

Official sources checked on 17 September 2026:

- [API and demo access](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes)
- [Terms and conditions](https://eodhd.com/financial-apis/terms-conditions)
- [Commercial versus personal use](https://eodhd.com/financial-apis/commercial-vs-personal-license-use)

## What is real, and what is simulated?

| Input or result | Origin |
| --- | --- |
| Historical Apple/Amazon prices | EODHD responses downloaded from its API |
| Buy 10 Apple shares; short 5 Amazon shares | Simulated trades, never actual orders |
| Execution prices | Hypothetical fills at the first day's provider close |
| Opening USD 10,000 cash; next-day settlement | Explicit simulation assumptions |
| Broker/admin comparisons | Separate scenario-specific arithmetic, not real counterparties |
| Holdings, cash and NAV | Calculated through our existing pipeline |

Using a daily close as a simulated fill does not prove a trade could have been
executed at that price. This narrow scenario assumes no corporate actions,
fees, borrowing costs or additional trades over the three dates; it does not
download or validate a corporate-action feed.

## Currency matters

These instruments are quoted in **USD per share**. The new scenario stays in
USD; it is not the GBP-reporting fund with a hidden exchange-rate assumption.
The shared cash, NAV, reconciliation and candidate functions now accept an
explicit currency, defaulting to GBP for the original lessons. They require
all relevant inputs to match that currency. There is no FX conversion yet.
Use a separate publication database for the USD scenario; the code rejects
mixing currency scenarios in one publication database.

## Download, build, and run in PowerShell

```powershell
$market = python -m data_extraction.market_prices
$scenario = python -m fund_pipeline.build_hybrid --market-delivery "$market" | ConvertFrom-Json
python -m fund_pipeline.fund_nav --business-date 2025-01-06 --as-of 2025-01-08 --currency USD --delivery "$($scenario.nav_delivery)"
python -m fund_pipeline.reconcile --business-date 2025-01-06 --as-of 2025-01-08 --currency USD --delivery "$($scenario.nav_delivery)" --references "$($scenario.reference_delivery)"
```

Only the first command needs the internet. `$market` stores the saved response
folder. Reuse that path to rebuild the scenario without another download.
`$scenario` holds the new input delivery paths and provenance (where data came
from). Results remain NOT APPROVED.

To prepare a candidate for local review, with its own USD database:

```powershell
$candidate = python -m fund_pipeline.publication --database data/hybrid_publication.sqlite prepare --business-date 2025-01-06 --as-of 2025-01-08 --currency USD --delivery "$($scenario.nav_delivery)" --references "$($scenario.reference_delivery)"
python -m fund_pipeline.publication --database data/hybrid_publication.sqlite show --candidate "$candidate"
```

This saves a candidate; it does not approve or publish it. The Part 7 review
workflow still applies to the explicitly labelled local learning scenario.

## Follow one observation through the code

1. `market_prices.download()` requests each symbol with fixed date boundaries,
   a timeout, and at most three attempts for temporary network/server errors.
   HTTP 429 receives bounded backoff; authentication failures are not retried.
2. The original bytes are saved before validation. `normalize()` checks fields,
   date coverage, uniqueness, positive prices, daily ranges and volume.
3. It writes `closing_prices.csv` in our existing shape: valuation date,
   instrument, currency and close price. Provider symbol names are retained.
4. A manifest records the public request URLs, receipt times, selected field,
   usage scope and file checksums. It appears only after both symbols succeed.
5. `build_hybrid()` verifies the raw and normalised data agree, creates simulated
   activity, and saves NAV/reference deliveries with links to the market input.
6. Existing quantity, settlement, valuation and reconciliation controls run in
   USD. Dollar prices are never relabelled as pounds.

## Independent reference arithmetic

The scenario builder does not call `calculate_nav()` to create reference NAV.
It starts with USD 10,000 and adds the long's price change times 10 shares and
the short's price decline times 5 shares. Cash is separately worked from the
opening amount and the two simulated payments. Reference positions are 10 and -5.
This checks the integration through a second, narrow calculation; shared input
errors and shared conceptual mistakes can still pass. It is not external audit.

## Failures and replay

If a response is an API error, omits a required date, repeats a date or changes
expected fields, the download fails. Raw responses and `failure.json` remain for
investigation; there is no completed manifest, so the hybrid builder refuses it.
Changing a saved response or normalised file also fails verification.

The three expected dates are explicit for this lesson. We have not implemented
a general exchange calendar, pagination, arbitrary symbols, daily scheduling,
source revision monitoring or rate-limit accounting across multiple workers.
The demo token is public; private credentials are neither required nor read.

## Your exercise

Using the same saved NAV delivery, change `--as-of` from 8 January to 7 January.
Both trades have settled on either date. Explain which input makes NAV change
between the two closes. Then omit `--currency USD` and verify that the default
GBP calculation refuses the dollar inputs instead of silently mislabelling them.

The reference statements cover 8 January only. A different valuation date needs
its own independently prepared statements; do not reuse the 8 January references.
