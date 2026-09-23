# Part 3: where holdings come from

Previously, `positions.csv` simply told us how many shares we held. Now we
calculate share quantities from completed trades and their portfolio allocations.
This is a separate synthetic scenario: it starts with zero holdings, unlike
Part 1's already-settled balances. Do not combine its positions with Part 1 cash.

## Three terms

- **Execution:** a trade that actually happened. An order is only a request to
  trade; requested quantities must not become positions before execution.
- **Allocation:** how much of an execution belongs to a particular portfolio.
  One execution can be divided between multiple portfolios.
- **Position:** the resulting share quantity held by a portfolio in an instrument.

## Work it out before running

| Execution | Action | Portfolio allocation | Position afterwards |
| --- | --- | --- | --- |
| E001 | Buy 100 ALPHA | A001: 100 to GROWTH | GROWTH owns 100 ALPHA |
| E002 | Sell 30 ALPHA | A002: 30 to GROWTH | GROWTH owns 70 ALPHA |
| E003 | Sell 20 BETA | A003: 20 to HEDGE | HEDGE is short 20 BETA |

Input quantities are positive. BUY adds shares; SELL subtracts them.
The negative BETA position means shares are owed. We assume borrowing is
permitted in this fixture; the code does not establish borrowing availability.

## Run it in PowerShell

```powershell
$trades = python -m fund_pipeline.landing --business-date 2026-09-14 --bundle trades
python -m fund_pipeline.build_positions --business-date 2026-09-14 --delivery "$trades"
```

The `trades` bundle contains `executions.csv` and `allocations.csv`. The landing
code saves and verifies them using the same receipt approach as Part 2.
Your output includes:

```text
GROWTH / ALPHA: 70 shares
HEDGE / BETA: -20 shares
Repeated executions ignored: 0
Repeated allocations ignored: 0
```

## Follow E001 through the code

1. `verify_delivery()` checks that the saved trade files match their manifest.
2. `read_events()` reads E001 and stores it under its execution ID. An exact
   repeat increments a duplicate counter but does not add another execution.
3. Allocation A001 refers to E001 and assigns its 100 shares to GROWTH.
4. `build_positions()` adds 100 to the `(GROWTH, ALPHA)` total because E001 is
   a BUY. E002's allocation later subtracts 30, leaving 70.
5. Before returning any positions, the code checks that allocations sum to the
   executed quantity for every execution. E001 must allocate exactly 100 shares.

Positions come from allocations. Adding execution quantities again would count
the trade twice. Prices and cash are unnecessary for this quantity calculation.

## Failures this prevents

| Input problem | Behaviour |
| --- | --- |
| Exact repeated execution/allocation ID and fields | Ignore its extra financial effect; report the repeat count |
| Same ID with changed fields in this delivery | Stop; source correction rules are not implemented |
| Allocation refers to an execution we do not have | Stop |
| Allocations total 99 or 101 for a 100-share execution | Stop |
| Wrong date, unknown side, invalid quantity or malformed record | Stop |

Different IDs represent different business events, even if their quantities
match. IDs belong to one simulated source in this lesson. Later, source identity
will also be part of the key.

## Exercise: retry the same trade

Copy the E001 data row in the **source** executions file and paste it as an extra
row at the end. Likewise duplicate A001 in the source allocations file. Save a
new trade delivery and run the position builder against it.

Predict the result first: ALPHA should remain 70 shares, with both repeat counts
equal to 1. The saved files still contain the repeated rows as evidence.
Remove the extra source rows afterwards so the original fixture stays unchanged.

## Limits and next lesson

This is a full rebuild from zero opening holdings for one date. It does not
append positions to a database, carry yesterday's holdings forward, or combine
multiple deliveries. Replaying the same complete delivery produces the same
positions. It is not a persistent, incremental event-processing system.

Changed IDs across deliveries cannot yet be resolved as corrections. We have
not implemented order validation, execution prices, cost basis, settlement,
cash, fees, corporate actions or approval. Signed quantity arithmetic can cross
zero, but this lesson makes no claim about the accounting or P&L of that change.

Next we will introduce execution prices and cash/settlement rules, with worked
examples, before joining these trades into a complete fund NAV calculation.
