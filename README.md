# Northbridge: learning to build a daily fund pipeline

## Current status

The Snowflake development build carries simulated holdings across 23 market
days, values them using real closing prices, tracks settlement confirmations,
applies investor flows and expenses, and calculates cash and a simplified USD
NAV for two accounts. ECB rates provide EUR/GBP reporting views, Treasury rates
provide a non-accounting cash benchmark, and a simulated bank feed checks cash.

The larger replay contains 3,200 trades across 20 stocks, including missing and
late confirmations and a day without trades. The replay also includes a fictional Mastercard dividend receipt. A separate Python
calculation checks all 920 position valuations and 46 account-day balances.

The local simulator produces five validated fictional trade events. A separate
Massive download contains 247,958 daily records across 503 tickers. Applying eight
reviewed history repairs produces an assembled dataset of 250,036 rows. It is
loaded into RAW.HISTORICAL_PRICES and typed by dbt's stg_historical_prices view.

- [Snowflake setup and ingestion](snowflake/README.md)
- [Multi-day replay: models, assumptions and one-command run](docs/multi_day_replay.md)
- [Active dbt model inventory and archived lessons](dbt/MODEL_INVENTORY.md)
- [Settlement lesson runner](docs/run_settlement_lesson.md)
- [Remaining work](docs/ROADMAP.md)
- [Production gap audit and build order](docs/PROJECT_AUDIT.md)
- [Snowflake governance model](docs/snowflake_governance.md)
- [Daily production operation and evidence](docs/daily_operations.md)
- [dbt setup](dbt/README.md) and [key authentication](dbt/KEY_AUTH.md)
- [Position valuation](dbt/VALUATION.md)
- [Simulator: produce five fictional trade events](docs/simulator.md)
- [Historical price downloads and resume instructions](docs/historical_prices.md)
- [Massive extraction scripts and commands](data_extraction/README.md)
- [Assembled historical prices](docs/assembled_prices.md)
- [Historical price staging](dbt/HISTORICAL_PRICES.md)
- [BNY identity checks and repair](docs/bny_identity.md)
- [Review of the remaining short histories](docs/coverage_review.md)

This is a learning project with a working production-style close, rather than a
live fund service. The current Snowflake
NAV includes the reviewed Mastercard dividend, investor flows and administrator
expenses. Borrow costs, margin and unapproved corporate actions remain excluded.
See [the final source integrations](docs/final_sources.md).
The lessons below also document the earlier Python prototype. A suspended
Snowflake task graph and native dbt project are implemented; its account-level
execution privilege must be approved before the task smoke test and schedule.
Fixtures are fictional. Downloaded market data and private keys stay outside Git.
The numbered lessons and pre-trial checklist preserve the earlier learning work.

## Code folders

| Folder | Purpose |
| --- | --- |
| data_extraction/ | Massive downloads, identity checks, repairs and assembly; earlier market and FX downloaders |
| simulation/ | Fictional trade-event producer |
| fund_pipeline/ | Earlier Python holdings, cash, NAV, reconciliation and daily runners |
| scripts/ | Local dbt connection and key setup |
| dbt/ | Snowflake transformations and data tests |
| snowflake/ | Database setup and ingestion SQL |
| tests/ | Python tests |

Run Python modules from the project root, for example:

```powershell
python -m simulation.simulator
python -m data_extraction.assemble_prices
python -m fund_pipeline.run_daily --help
```

Existing data, fixtures, configuration and calendars retain their locations.
Saved historical manifests retain their original code fingerprints; new runs
record the reorganised source paths and hashes.

## Earlier Python prototype

We are building this in small lessons. We now have a calculation we can check
by hand, saved input deliveries that can be replayed, and positions derived
from allocated trades. Part 4 adds cash, outstanding obligations and confirmed
settlements. Part 5 connects those results to dated closing prices to calculate
NAV. Part 6 compares these results with hand-worked synthetic broker and
administrator statements. Part 7 adds saved candidates, recorded local approval
and versioned publication. It is not yet an automated pipeline or a production system.

[Part 8: real historical prices](docs/lesson_08_real_prices.md) adds our first
external source, preserving raw responses and testing missing/malformed data.
[Part 9: GBP reporting with ECB rates](docs/lesson_09_fx.md) translates the USD
scenario into GBP while preserving the original amounts. This reporting output
is not yet integrated with GBP reconciliation or publication.

## Part 1: value one day's holdings

A **position** is how many shares we hold. A **long** position means we own
shares; a **short** means we sold borrowed shares and still owe those shares.
We represent shorts with a negative quantity.

**Market value** is quantity multiplied by the closing price.
**NAV (net asset value)** is the fund's assets less its liabilities.
For this deliberately small example, NAV is cash plus signed market values.

| Holding | Shares | Closing price (GBP) | Market value (GBP) |
| --- | ---: | ---: | ---: |
| ALPHA | 100 | 10.50 | 1,050.00 |
| BETA | -20 | 18.00 | -360.00 |
| Cash | | | 9,400.00 |
| **Fund NAV** | | | **10,090.00** |

The cash comes from a hand-worked setup: start with GBP 10,000, buy 100 ALPHA
shares for GBP 10 each, and short 20 BETA shares for GBP 20 each.
Cash becomes 10,000 - 1,000 + 400 = 9,400. Those trades have already settled
before this example's business date. Part 1 supplies their resulting balances
directly; Part 4 implements settlement in a separate scenario. Short proceeds
are included in accounting cash; that does
not mean all the cash is available to spend.

At the starting prices, NAV was 9,400 + 1,000 - 400 = 10,000.
ALPHA then gains GBP 50; BETA's short obligation falls by GBP 40.
With no trades, fees or investor flows today, closing NAV is GBP 10,090.

### Run it

From this folder, using Python 3.12 (no dependencies to install yet):

```powershell
python -m fund_pipeline.daily_close --business-date 2026-09-14
python -m unittest discover -s tests -v
```

The **business date** is the day the numbers describe. We pass it explicitly
so tomorrow we can rerun yesterday's close without changing the code.

### Follow one record

1. `fixtures/2026-09-14/positions.csv` says GROWTH holds 100 ALPHA shares.
2. `prices.csv` supplies ALPHA's closing price: GBP 10.50 per share.
3. `calculate_close()` matches the records by instrument and multiplies them.
4. GBP 1,050 joins BETA's GBP -360 and cash of GBP 9,400 in the fund total.

The code uses `Decimal`: decimal arithmetic avoids binary floating-point
surprises when calculating money. CSV values stay as text until conversion.
One function reads and checks the date; another calculates the close.

**Failure we prevent:** a missing price must stop the calculation. Treating an
unpriced holding as zero would produce a believable but wrong fund value.
Duplicate position or price keys also stop it; adding repeated rows could
otherwise double the fund's holdings.

### Your exercise

Before changing anything, predict NAV if BETA's closing price rises from
GBP 18 to GBP 19. Then edit its price and rerun. Explain why the fund loses
money when that share price rises. Restore GBP 18 before running the tests.

## Where we go next

1. **Built:** read three small files, value long/short holdings, verify the result.
2. **Built:** land deliveries safely and record which files a close used. A
   *delivery* is a batch of records received from one source.
   Follow [Part 2: saving and replaying inputs](docs/lesson_02_landing.md).
3. **Built:** derive quantities from executions and allocations.
   An *execution* is a completed trade; an *allocation* assigns its quantity
   to a portfolio. Follow [Part 3: building holdings](docs/lesson_03_positions.md).
   This separate scenario starts from zero holdings. Order validation is pending.
   [Part 4: cash and settlement](docs/lesson_04_settlement.md) adds execution
   prices, opening cash, confirmations, receivables and payables.
   [Part 5: trade-derived NAV](docs/lesson_05_nav.md) joins these results to
   dated closing prices and produces GBP 10,105 in this limited scenario.
4. **Built:** compare our results with independently prepared broker/admin fixtures.
   This comparison is called *reconciliation*. Follow
   [Part 6: reconciliation and an intentional mismatch](docs/lesson_06_reconciliation.md).
   Passing checks alone do not approve or publish a result.
   [Part 7: local approval and publication](docs/lesson_07_publication.md) adds
   separate review records and preserves each published version in SQLite.
5. Prepare and validate the local model and cloud design, then review readiness.
6. After explicit cloud authorisation, load Snowflake, transform with dbt,
   and schedule daily runs with a Snowflake task graph.
7. Add a daily dashboard and evaluate unusual-trading-activity detection.
   Start with simple rules, then compare Isolation Forest using earlier dates
   for training and later dates for evaluation. Synthetic results will be
   labelled; they do not prove detection performance on real fund activity.

At each step we will inspect inputs, outputs and an intentional failure.
[Part 22: sourced valuation calendar](docs/lesson_22_exchange_calendar.md) adds
a pinned January 2025 calendar with holidays, exceptional closures and saved lineage.
[Part 21: weekday calendar](docs/lesson_21_weekday_calendar.md) supports Friday-to-Monday
closes, requires fresh daily inputs and processes weekend settlement confirmations.
[Part 20: processing a new day](docs/lesson_20_new_day.md) demonstrates 10 January:
unchanged holdings, a settled payable and a new closing price.
[Part 19: daily USD runner](docs/lesson_19_daily_runner.md) runs the carry-forward
close from configuration and reuses a successful candidate on identical retries.
[Part 18: daily publication](docs/lesson_18_daily_publication.md) saves the next-day
USD candidate for review and carries its published ledger into subsequent dates.
[Part 17: next-day reconciliation](docs/lesson_17_daily_reconciliation.md) checks
simulated broker/admin statements and blocks an intentional one-share mismatch.
[Part 16: next-day NAV](docs/lesson_16_daily_nav.md) combines carried holdings,
cash and obligations with labelled teaching closing prices.
[Part 15: daily cash](docs/lesson_15_daily_cash.md) carries cash and unpaid trade
obligations forward, applying settlement confirmations once.
[Part 14: opening holdings](docs/lesson_14_opening_holdings.md) carries a published
day's share quantities into the next day's simulated trades.
[Part 13: run configuration](docs/lesson_13_configuration.md) shortens the saved
historical run to `python -m fund_pipeline.run_pipeline --config configs/close_2025-01-08.json`.
[Part 12: safe reruns](docs/lesson_12_reruns.md) reuses successful candidates for
unchanged dates, saved deliveries and calculation code while logging each attempt.
Use [Part 11: one pipeline command](docs/lesson_11_pipeline.md) to run the saved
USD/GBP inputs end to end and leave a candidate ready for review.
The GBP translation now has [Part 10: GBP checks and approval](docs/lesson_10_gbp_approval.md),
including saved FX evidence and reviewed correction versions.
Use [the design](docs/design.md), [calculation rules](docs/business_rules.md)
and [readiness checklist](PRE_TRIAL_READINESS.md) for the wider plan.
