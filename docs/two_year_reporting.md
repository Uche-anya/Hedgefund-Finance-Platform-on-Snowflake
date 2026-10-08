# Two-year exploratory reporting extract

Run `scripts/build_two_year_reporting.py` after building a versioned action
decision ledger. It reads the ledger's daily close, the saved position rows,
and the dated instrument seed. It writes two CSV files under
`data/two_year_reporting/<ledger_id>/`:

| File | One row means | Use it for |
| --- | --- | --- |
| `account_day.csv` | One account on one market day | NAV components, cash, long/short and gross exposure |
| `position_day.csv` | One security held by one account on one market day | Holdings, ticker and concentration |

The shared keys are `scenario_id`, `ledger_id`, `business_date`, and
`account_id`. `position_day.csv` adds `security_id` to its key. The security
name and ticker come from the instrument record valid on **that day**, so a
later ticker change does not rename older rows. A position's market value is
shares times that day's unadjusted close. For each account-day, the script
checks that signed position values add back to the market value in the close.

The account table keeps two NAV figures. `reviewed_nav_usd` excludes pending
corporate-action candidates. `illustrative_nav_usd` includes them, and their
difference is `pending_candidate_impact_usd`. Both remain provisional. The
ratios are decimals: `0.25` means 25%, not 0.25%. A short position has a
negative signed NAV weight but a positive absolute share of gross exposure.

The original `TWO_YEAR_REVIEW_001` extract has 1,000 account-day rows and
19,534 position-day rows. Its manifest contains input and output hashes.
`TWO_YEAR_REVIEW_003` has the same row counts after the reviewed PepsiCo
entitlement is included; 142 other dividend events remain pending. The
original extract is retained for before-and-after comparison.
Keep the two tables at their stated grains in Power BI: joining the account
NAV directly to every position row and then summing NAV would multiply it by
the number of positions. Relate them on the four shared keys and calculate
account totals from `account_day.csv`.

Ledger 003 is also loaded into `NORTHBRIDGE_DEV.RAW.TWO_YEAR_REPORTING` as a
manifest-checked snapshot. dbt serves it as
`NORTHBRIDGE_DEV.DBT_DEV.CMP_PYTHON_ACCOUNT_DAY` and
`CMP_PYTHON_POSITION_DAY`. Both comparison views keep `ledger_id`, the manifest hash,
and `reporting_status = EXPLORATORY_PROVISIONAL`. The Snowflake copy has 1,000
account-days and 19,534 position-days from 23 September 2024 to 21 September
2026. Its summed reviewed account-day NAV is USD 4,909,683,594.885; this is
a sum of 1,000 daily balances for a load check, **not** one fund NAV or a
performance measure. The account and position market values both sum to
USD -60,519,279.075 across the full history. The dbt grain and valuation
checks pass, including the opening day when neither account owns stocks.

To rebuild this copy from the saved local extract, run the checked loader and
then the selected dbt models:

```powershell
.\.venv\dbt\Scripts\python.exe -m scripts.load_two_year_reporting TWO_YEAR_REVIEW_003
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select 'cmp_python_account_day cmp_python_position_day'
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select two_year_serving_checks
```

The last command runs separately because dbt's cautious model selection does
not automatically select a test that also reads a raw source. `snowflake/50_two_year_reporting.sql`
creates the landing objects; `snowflake/51_two_year_reporting_checks.sql`
prints the totals for comparison with the saved CSVs.

This is an exploratory dataset, not published fund performance. The latest
ledger still has 142 pending dividend actions, limited bank and payment evidence,
and no borrow fees or tax. We have left daily returns and drawdowns out of
this extract until investor flows and accounting completeness are checked
for the full two-year period. The extract tables above are comparison evidence.
For new analysis use the RAW-derived `FCT_ACCOUNT_NAV_DAILY` and
`FCT_ACCOUNT_POSITIONS_DAILY` described in
[the Snowflake path](two_year_snowflake_path.md).
