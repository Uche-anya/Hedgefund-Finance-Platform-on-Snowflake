# Part 15: carry cash and unpaid trades into the next day

Buying shares creates a payment obligation. Cash leaves only when settlement is
confirmed. We now carry both yesterday's settled cash and its unpaid obligations
into a new day, so yesterday's unpaid trades are not forgotten.

## Our 9 January example

The published opening contains USD 8,688.05 cash. Its GBP cash value is only a
reporting translation: we must use the original USD cash for USD settlements.

Today's prices below are invented execution prices for simulated trades.

| Trade | Amount | Confirmation today | Effect |
| --- | ---: | --- | --- |
| Buy 3 Apple at USD 240 | USD 720 | None | Add a payable of USD 720 |
| Buy back 2 Amazon at USD 220 | USD 440 | Confirmed | Deduct USD 440 from cash |

    Closing cash = 8,688.05 - 440.00 = USD 8,248.05
    Closing payable = USD 720.00

The Amazon settlement is deliberately simulated as an early, same-day settlement;
it is not a claim about the usual equity settlement timetable. Both trades have
a stated due date of 10 January. A due date alone never moves cash.

Cash plus receivables minus payables is USD 7,528.05. This subtotal excludes share
values, so it is neither NAV nor a measure of available buying power.

## What happens to the unpaid Apple purchase tomorrow?

The next day starts with the USD 720 payable still present. If settlement is
confirmed, deduct USD 720 and remove the payable together. Without confirmation,
keep it. Our existing end-of-day rule marks it OVERDUE on its due date.
A carried receivable works in the opposite direction: settlement increases cash
and removes the amount owed to us. Tests cover both carried payables and receivables.

## Run it

```powershell
$delivery = python -m fund_pipeline.landing --business-date 2025-01-09 --bundle daily_cash
python -m fund_pipeline.carry_cash --database data/gbp_publication_demo.sqlite --previous-date 2025-01-08 --business-date 2025-01-09 --delivery $delivery
```

This uses Part 10's existing local demonstration publication. It does not approve
anything under your name. A fresh checkout needs a published opening first.
The new bundle contains executions, allocations, execution terms and settlement
confirmations. Opening cash is read from the published close, not typed into a
second opening-cash CSV. The result is saved under `data/cash/` as CASH ONLY - NOT
APPROVED with its source publication/version and new delivery fingerprint.

## Avoiding duplicate deductions

The fixture contains the exact Amazon settlement row twice. It is counted once.
Two different confirmations for the same obligation cause an error. Once an
obligation is removed, a later day's replay of its confirmation also causes an
error: it has no open obligation to settle. It never causes another deduction.

Every calculation starts from an unchanged opening snapshot. Repeating a run
therefore gives the same cash result. New trades cannot reuse execution IDs
already recorded in the opening history. The returned cash state carries those
IDs forward. Settlement IDs are deduplicated within each day's batch; there is
not yet a global, provider-scoped settlement event registry.

Amounts and currencies must match their obligations. This first daily batch
accepts only full settlements on the batch's business date. Future-dated and
backdated confirmations are rejected; handling late-arriving historical corrections
requires a later replay policy. Opening payable/receivable totals must match their
individual obligations before processing begins.

## Reading the code

`carry_cash` loads a published opening and its original trade history, selects the
original local currency when the close was translated, verifies the new delivery,
and calls `roll_cash`.

`roll_cash` copies open obligations, adds today's trade obligations, then applies
settlements. It returns a new cash state without changing its opening argument.
Tests pass this returned state to a subsequent day to check carry-forward and replay.

The command currently starts from the original single-batch published close. A
future integrated daily close must persist its complete execution history for
subsequent published days; it must not rebuild that history from only the latest
day's trades. Today's cash-only report cannot yet be published or used as a full
approved opening close by the command.

## Scope

Consecutive calendar days and one settlement currency only. No fees, partial
settlements, corporate actions, funding/credit checks or automatic correction
propagation. Cash can be negative in this accounting calculation; it does not
assert that a broker would permit the transaction. Holdings from Part 14 and cash
from this lesson still need to be joined to prices, reconciliation and publication
to form the next full daily close.
