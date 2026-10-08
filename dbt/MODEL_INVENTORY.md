# Active dbt model inventory

The active graph calculates the two-year provisional equity close for
`sim-equity-2024-2026-v2`.

| Layer | Model | One row means |
| --- | --- | --- |
| Staging | `stg_oms_events` | One OMS execution event in RAW |
| Staging | `stg_settlement_events` | One custodian settlement event in RAW |
| Staging | `stg_historical_prices` | One dated stock-price row in the selected provider delivery |
| Staging | `stg_corporate_actions` | One provider action after saved event review |
| Intermediate | `int_market_days` | One market date in the selected price deliveries |
| Intermediate | `int_trade_obligations` | One active execution, with a settlement if confirmed |
| Mart | `fct_account_positions_daily` | One account, security and market date, calculated from trades and prices |
| Mart | `fct_account_cash_daily` | One account and market date of settled cash and open trades |
| Mart | `fct_account_dividends_daily` | One account and market date of approved and pending entitlements |
| Mart | `fct_account_nav_daily` | One account and market date of provisional NAV |
| Comparison | `cmp_python_account_day` | A saved Python account-day row, used only for parity checks |
| Comparison | `cmp_python_position_day` | A saved Python position-day row, used only for parity checks |

`dim_instrument` is the dated security map. `reviewed_action_decisions` holds
the four saved dividend review decisions. `approved_corporate_actions` remains
as legacy evidence because the versioned Python close still reads its saved
Mastercard approval; no active dbt model uses that seed.

The three `two_year_*_matches_saved_close` tests compare every calculated
position, cash and NAV row in ledger `TWO_YEAR_REVIEW_003`. Those tests are
fixtures limited to the saved 500 dates, not production acceptance rules.
The `cmp_python_*` models are tagged `fixture`; daily builds exclude them.
The historical scenario ID remains in the source records as lineage. The dbt
model names describe their row grain and do not depend on the history length.
After the 22 September daily extension, the RAW-derived tables contain
19,574 position-days and 1,002 account-days.

The short replay's old `DAILY_CLOSE` task and rebuildable dbt relations were
retired from the development account.
