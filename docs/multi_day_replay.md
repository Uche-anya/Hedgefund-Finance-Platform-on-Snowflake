# Replay several days of fund activity

This development run combines saved Massive prices with fictional trades and
custodian confirmations. It covers 6–30 January 2025: 17 valuation days, 20 stocks
and two accounts. Each account starts with USD 5 million and zero shares.

There are 3,200 trades and 3,168 confirmations. Some confirmations arrive the next
day; 32 are deliberately absent. January 15 has no trades, so yesterday's shares
must carry forward while their market prices can change.

## Run it again

From the project root, with the existing Snowflake setup and saved inputs:

```powershell
python scripts/run_replay.py
```

The command checks input hashes, reloads the saved JSONL file, builds and tests
the dbt models, then compares Snowflake results with a separate Python Decimal
calculation. It stops on failure and saves a run record in `data/replay_runs`.
Snowflake skips the already-loaded file on a normal retry. The models rebuild
from the saved delivery; this command does not generate fresh trades.

The loader still uses the personal admin connection and may require MFA.
This is a replay command, not an unattended production scheduler or a fresh
account bootstrap. Historical prices and the reviewed corporate actions must already be loaded and accessible.
The runner now selects the full dividend continuation package through February 7.

## What each model does

| Model | One row represents | Calculation |
| --- | --- | --- |
| stg_activity_events | One input record | Extract JSON fields and convert dates and amounts |
| fct_daily_positions | Date, account, stock | Previous shares plus today's buys minus sells |
| fct_daily_valuations | Date, account, stock | Closing shares multiplied by that day's real close |
| fct_settlement_obligations | Date, account, execution | Expected payment and confirmation known by the cutoff |
| fct_daily_cash | Date, account | Opening cash, confirmed payments and outstanding amounts |
| fct_daily_nav | Date, account | Cash plus receivables minus payables plus signed position value |

A receivable is money owed to the account. A payable is money the account owes.
A missing confirmation remains outstanding; it is not automatically a failed
payment. A late report becomes visible only at a cutoff after publication.

The result contains 920 stock valuations and 46 account-day balances. Tests check
record counts, duplicate records, settlement details, position continuity and
cash/NAV arithmetic. The independent Python calculation checks every resulting
position and account-day balance, rather than only checking totals.

## Test scope

Required fields are checked within the input,
position, cash and NAV validation queries. Missing valuation prices retain a
separate test so an absent market price is easy to identify.

Fixed-data expectations carry the `fixture` tag. They cover snapshot counts,
replay outputs and the deliberate broker exceptions. `scripts/run_replay.py`
runs them. A routine processing build uses `--exclude tag:fixture`.

## Calendars and prices

Execution prices are fictional offsets from the previous market session's close.
Valuation uses the current session's saved unadjusted close. Both use the pinned
price snapshot, with its hash recorded in the replay manifest.

Market and settlement calendars differ. January 9 was an equity-market closure,
but DTCC remained open for settlement. The January settlement exceptions are
recorded in the configuration using the
[DTCC holiday schedule](https://www.dtcc.com/Globals/PDFs/2024/October/30/20972-24)
and [January 9 notice](https://www.dtcc.com/-/media/Files/pdf/2024/12/30/0275.pdf).
The original generator remains bounded to January. The dividend continuation appends
six sessions and one fictional cash receipt; no new trades are generated.

## Limits

The simplified NAV includes the reviewed Mastercard dividend, two investor
flows and administrator expenses. ECB rates translate the result for reporting;
the Treasury yield remains a non-accounting benchmark. Other dividends, stock
splits, borrow costs and margin remain excluded. Random trades do not represent an investment strategy.
The current stock universe also does not reconstruct historical index membership.
These results demonstrate pipeline accounting, not investment performance.

Confirmations come from the simulator's own trade inputs. They exercise missing
and delayed-message handling, but do not prove reconciliation with an independent
broker. Snowflake Tasks, continuous ingestion and ML remain separate upcoming work.

For the dividend assumptions and daily balance treatment, see [Mastercard dividend](mastercard_dividend.md).
