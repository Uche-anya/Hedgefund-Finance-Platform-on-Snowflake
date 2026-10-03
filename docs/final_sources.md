# Final source integrations

The project stops at eight logical sources. Public reference data is preserved
as received; private fund operations are clearly labelled simulations.

| Source | Real or simulated | Records in the saved delivery | Downstream use |
| --- | --- | ---: | --- |
| Massive daily stock prices | Real | 250,036 | Position valuation |
| Massive corporate actions | Real plus reviewed decisions | 3,271 raw rows | Dividend accruals |
| OMS and custodian activity | Simulated | 6,394 | Positions, settlements, cash and NAV |
| Prime-broker positions | Simulated | 40 | Position reconciliation |
| ECB reference rates | Real | 23 | EUR and GBP reporting NAV |
| US Treasury one-month rates | Real | 23 | Non-accounting cash-yield benchmark |
| Fund administrator events | Simulated | 4 | Investor flows, expenses, cash and NAV |
| Bank closing balances | Simulated | 2 | Cash reconciliation |

## Accounting boundary

Investor subscriptions and redemptions change cash and total NAV. Expenses
reduce NAV when accrued; payment later moves the liability into cash without a
second expense. The bank statement independently checks settled cash.

ECB rates change reporting currency only. They do not change the USD books.
Treasury rates are labelled `NON_ACCOUNTING_TREASURY_BENCHMARK`: a government
yield is useful for analytics but does not prove that a bank paid interest.

## Saved deliveries

Each delivery has a manifest, record count and SHA-256 file hash. The restricted
ingestion user loads the JSONL records into append-only raw tables. dbt selects
one delivery ID per source, types the records and runs the contracts before the
mart tables build.
