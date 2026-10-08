# Building the longer fund scenario

The saved market file contains 500 common closing-price dates for the 20 stocks
used here. We will replay one business date at a time rather than upload a
single two-year trade file. Historical event timestamps describe the simulated
business day; `loaded_at` records when Snowflake actually received the file.
Those are different clocks.

## First pilot: five days

`config/two_year_pilot.json` selects September 24–30, 2024. The first saved
market date, September 23, supplies the prior close for September 24. The
producer makes four fictional fills per day, split across two accounts. Event
IDs, execution IDs, delivery IDs and file contents are stable on rerun.

For one day:

```powershell
.\.venv\dbt\Scripts\python.exe -m simulation.daily_oms --day 2024-09-24
.\.venv\dbt\Scripts\python.exe scripts\load_oms_snowpipe.py data\daily_oms\sim-equity-2024-2026-v1\2024-09-24\oms.jsonl --delivery-id oms-sim-equity-2024-2026-v1-20240924
```

The producer saves a manifest and an OMS JSONL file. The loader validates the
events, uploads the file to Snowflake's internal stage, calls Snowpipe's
`insertFiles` API, waits for RAW rows, and records a READY delivery. This is
real Snowpipe ingestion using its REST notification route. It is not automatic
cloud-storage notification; a scheduled producer or service would call the
loader in production. Snowflake describes this internal-stage REST flow in its
[Snowpipe loading guide](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-rest-load).

The five saved pilot deliveries were loaded and checked against their manifests:
four fills on each date, 20 in total. `STG_OMS_EVENTS` built successfully and
its event-ID and execution-ID checks passed. An exact September 24 retry still
left four RAW rows. Run the read-only comparison again
with:

```powershell
.\.venv\dbt\Scripts\python.exe scripts\check_daily_oms_pilot.py
```

## What happens after an OMS delivery

```text
simulated OMS -> dated JSONL -> internal stage -> Snowpipe -> RAW.OMS_EVENTS
simulated custodian -> settlement delivery -> Snowpipe -> RAW.SETTLEMENT_EVENTS
market prices + reviewed actions + fund admin + broker + bank -> daily readiness gate
ready day -> dbt positions, cash, NAV and reconciliations -> human review
approved curated results -> Power BI semantic model
```

The second line now uses `SETTLEMENT_EVENTS_PIPE`, another internal stage and
Snowpipe REST notification. The producer writes one custodian file for each
settlement date; the five OMS trade dates produce five settlement files, the
last dated October 1. All 20 confirmations loaded into RAW and each delivery
has a READY receipt. `STG_SETTLEMENT_EVENTS` and its three basic dbt checks
passed.

For a new batch, generate the custodian files after saving the OMS files, then
load each settlement date separately. For example:

```powershell
.\.venv\dbt\Scripts\python.exe -m simulation.daily_settlements
.\.venv\dbt\Scripts\python.exe scripts\load_settlement_snowpipe.py data\daily_settlements\sim-equity-2024-2026-v1\2024-09-25\settlements.jsonl --delivery-id settlement-sim-equity-2024-2026-v1-20240925
```

The pipe itself is defined in `snowflake/48_settlement_snowpipe.sql` and needs
to be created once per environment. Repeating the September 25 load kept four
RAW rows and the same READY receipt.

The test close reads the two RAW feeds back from Snowflake, compares each row
with its saved file, checks each confirmation against the trade due that day,
and uses the saved market close and reviewed instrument map. It begins on
September 23 with a **fictional USD 5 million subscription in each account**
recorded by the fund administrator and a separate bank statement showing the
same cash. Both files were loaded into Snowflake RAW through the existing batch
loader. The close reads those RAW rows and refuses to start if the accounts,
dates, currencies or amounts differ. Generate and load the opening with:

```powershell
.\.venv\dbt\Scripts\python.exe -m simulation.pilot_opening
.\.venv\dbt\Scripts\python.exe scripts\load_daily_inputs.py --config data\daily_opening\sim-equity-2024-2026-v1\2024-09-23\load_config.json
```

These two fictional opening files are generated from the same scenario
assumption. Their match tests the integration and reconciliation logic; it is
not independent bank evidence.

It carries shares, settled cash and unsettled trade cash from one date to the
next. The September 24 close has four open trade obligations. On September 25,
those four settle and four new trades leave four obligations open. This pattern
continues through September 30. The October 1 confirmations were loaded, but
were not included in the September 30 close.

Run the repeatable read-only calculation with:

```powershell
.\.venv\dbt\Scripts\python.exe scripts\close_daily_pilot.py
```

The revised results are saved under
`data/daily_close/bank_opening_v1/<scenario>/<date>/` as `close.json`
and `next_opening.json`. They are explicitly marked `UNAPPROVED_TEST`. This
calculation is a pilot Python close, not yet the scheduled dbt NAV path. The
current dbt NAV marts still read the earlier `RAW.REPLAY_INPUTS` delivery.
The custodian data is a **separate fictional feed derived from OMS trades**;
it cannot prove an independent custodian agrees with us. The test also stops
if an approved corporate action falls on a pilot date, because this simple
close does not yet account for dividends or splits. We still need fund-admin
flows, independent broker and bank evidence, a daily readiness gate, and a
reviewed dbt/Power BI serving layer before replaying all 500 market dates.

The producer uses yesterday's close with a small fictional offset as its
execution price. That avoids using tomorrow's market price to choose today's
trades, but these are not real execution quotes or evidence of an investable
strategy. The price-date list is also not an independently reviewed exchange
calendar; the full run needs that calendar, corporate-action coverage, and
longer FX and Treasury deliveries. All fund performance remains simulated.

## Two-year raw backfill

The full config extends the **same scenario** through 18 September 2026. The
saved price series ends on 21 September. September 23, 2024 is the opening
date; the 498 dates between those endpoints have trades; the last date gives
the September 18 trades a settlement date. That makes 500 possible market-day
closes for each of the two accounts, once the accounting is complete.

```powershell
.\.venv\dbt\Scripts\python.exe -m simulation.daily_oms --config config\two_year_replay.json
.\.venv\dbt\Scripts\python.exe -m simulation.daily_settlements --config config\two_year_replay.json
.\.venv\dbt\Scripts\python.exe scripts\audit_two_year_replay.py
.\.venv\dbt\Scripts\python.exe scripts\prepare_two_year_backfill.py
.\.venv\dbt\Scripts\python.exe scripts\load_two_year_backfill.py
```

The audit found 498 dated OMS files with 1,992 fills and 498 custodian files
with 1,992 matching confirmations. To avoid 986 Snowpipe notifications for old
tiny files, the backfill combines the 493 dates that were not in the pilot into
one OMS file and one custodian file. It uses `COPY INTO` to load those saved
historical files and keeps their original daily delivery IDs. The five pilot
dates retain their Snowpipe history. Future daily arrivals continue to use the
Snowpipe loaders. Snowflake documents basic transformations and file metadata
in [COPY INTO](https://docs.snowflake.com/en/user-guide/data-load-transform).

Snowflake now has 1,992 RAW rows and 498 READY daily receipts for **each** of
the two event sources. Repeating the bulk load left both row counts unchanged
and added no receipts. The OMS and settlement dbt staging views rebuilt with
all six selected data tests passing.

This is **not a two-year NAV series yet**. The saved corporate-action source
contains 144 raw dividend candidates for these 20 stocks in the period, while
the current approval seed contains only one of their IDs. A provider candidate
does not by itself establish that an account earned or paid a dividend. XOM
also changes to a successor security in July 2026; existing shares must be
carried across that transition. We must settle those accounting rules before
calculating and publishing two-year performance. The next step is to review
the actions, implement dated entitlement and security-transition handling,
then build and reconcile the 500 daily closes.

`scripts/prepare_two_year_dividend_review.py` writes
`data/two_year_dividend_review.csv` with the provider event ID, ex-date,
payment date, cash per share, source row and dated security ID. It found 144
candidate dividends: 143 marked `PENDING` and one already in the approval
seed. The August 2026 XOM row maps to the successor security `NB_EQ_0021`;
earlier XOM rows map to `NB_EQ_0015`. The file is a review queue, not an
instruction to pay cash or book all 144 entitlements.

## Provisional two-year close

`scripts/build_two_year_close.py` reads the loaded Snowflake OMS and custodian
rows back, matches their full payloads to the saved daily files, then reads
prices, security identities and candidate dividends from dbt staging. It
starts from the loaded September 23 bank and administrator opening records.

The calculation carries positions and settled cash through all 500 market
dates. On a dividend ex-date it uses the shares held **before that day's
trades**. A long position creates a gross receivable; a short position creates
a gross payable. There are no simulated dividend payment confirmations for
this long scenario, so these balances stay outstanding. The script does not
turn a provider payment date into cash. On 2 July 2026, it moves existing XOM
shares one-for-one from `NB_EQ_0015` to `NB_EQ_0021` using the provisional
transfer rule in `config/two_year_security_transfers.csv`.

```powershell
.\.venv\dbt\Scripts\python.exe scripts\prepare_two_year_dividend_review.py
.\.venv\dbt\Scripts\python.exe scripts\build_two_year_close.py
```

The immutable output under `data/two_year_close/provisional_v1/` has 1,000
account-day close rows, 19,404 nonzero account-security-day position rows,
288 account-level candidate entitlements and two XOM transfer rows. Every
row is marked `PROVISIONAL_UNAPPROVED`; the two-year result has not been
written to the approved dbt NAV marts or published for Power BI.

The illustrative NAV includes all candidate gross dividends, even though
143 provider action IDs still need review. It assumes no tax, withholding,
securities-lending charge or fund expense. The fund also has no daily bank
statements or independent dividend cash confirmations for this period. The
simulated trades are small relative to the USD 5 million opening balances,
so this run proves continuity and data volume more than realistic capital
deployment or fund returns. A separately versioned, reviewed scenario is
needed before using it as a compelling performance dashboard.

## Second scenario: dollar-sized trades

`config/two_year_replay_v2.json` uses a new scenario ID. It leaves all v1
deliveries alone. The trade producer still picks a stock and a buy or sell
side deterministically, but it now chooses a $25,000-$45,000 budget and
divides by the **previous** saved close to get whole shares. The fill price
then gets the same small fictional offset. This is a data-pipeline scenario,
not a trading strategy or a claim of historical fund returns.

The five-day v2 pilot was checked locally before upload. The complete local
sizing check then found 1,992 fills over 498 trade dates, with median gross
stock exposure of 72.61% of NAV, maximum 106.20%, and minimum settled cash
of $4,785,224.13 across the two accounts. Gross exposure is the sum of the
absolute values of long and short positions divided by NAV. These figures
exclude dividends, tax, borrow fees and daily bank reconciliation; they are
guardrails for simulated trade sizes, not approved risk figures.

The v2 opening administrator and bank files were loaded separately. Five OMS
and five custodian pilot files went through the internal-stage Snowpipe path.
The remaining 493 dates for each source went through the historical `COPY`
path. Snowflake RAW now has 1,992 v2 OMS rows and 1,992 v2 settlement rows,
each source with 498 READY daily receipts. Repeating the bulk load added no
receipts. The two dbt staging views and six selected tests passed.

`scripts/build_two_year_close.py --config config/two_year_replay_v2.json`
reads those v2 RAW rows and writes `data/two_year_close/provisional_v2/`.
It produced 1,000 account-day closes, 19,534 nonzero position rows, 288
candidate account-level dividend entitlements and two XOM security transfers.
Every close remains `PROVISIONAL_UNAPPROVED`. The 143 pending provider dividend
events still need review. The later one-event pilot below has not been applied
to the 500-day close, and most days still lack payment and bank evidence. The
provisional NAV must not be published as audited fund performance.

## One dividend payment pilot

The reviewed Mastercard event `Ec6372...b0b` has an ex-date of January 10,
2025 and a payment date of February 7. The v2 close shows 47 eligible shares
in account 01 and 58 in account 02. At $0.76 per share, the gross receivables
are $35.72 and $44.08. The event was already in the approved-action seed; this
pilot did not approve any of the other 143 candidate events.

`simulation/two_year_dividend_pilot.py` saves two fictional custodian payment
confirmations and two fictional February 7 bank balances. The bank values are
the provisional settled cash **plus** the matching payment. Both feeds are
derived from our own scenario, so a match demonstrates the join and cash
logic, not independent evidence that a real custodian or bank paid anything.
The files and their hashes are under
`data/dividend_payment_pilot/sim-equity-2024-2026-v2/2025-02-07/`.

`snowflake/49_dividend_payment_events.sql` creates a separate RAW payment
table and internal stage. The two pilot files were loaded through the existing
stage-and-`COPY` batch loader with READY receipts. The OMS and trade-settlement
feeds still use Snowpipe for daily arrivals; a production dividend feed would
need its own scheduled or Snowpipe ingestion path.

`scripts/reconcile_two_year_dividend.py` reads the loaded RAW rows, checks
their exact saved payloads and receipts, confirms the provider event in dbt
staging, then compares the cash with the accrual and bank balance. Both
accounts report `MATCHED`: the selected receivable is $0.00 after payment,
and the bank balance difference is $0.00. A missing payment, a short payment,
or a mismatched bank balance produces a different status. The result is in
`reconciliation_v2.json` in the pilot folder.

The original `provisional_v2/` close remains saved as the before-payment
comparison. To apply the confirmed cash in a separate close, run:

```powershell
.\.venv\dbt\Scripts\python.exe scripts\build_two_year_close.py --config config\two_year_replay_v2.json --apply-dividend-pilot
```

The resulting `data/two_year_close/provisional_v2_paid_ma/` has the same
1,000 account-day rows and the same positions. On February 7, account 01
cash rises from $5,035,867.03 to $5,035,902.75 while its dividend receivable
falls by $35.72. Account 02 cash rises from $4,826,374.77 to $4,826,418.85
while its receivable falls by $44.08. The two Mastercard entitlement rows
are marked `MATCHED`. The remaining aggregate receivable includes other
unconfirmed candidate dividends.

The builder checks that the payment and bank rows match their saved files and
READY receipts, that both bank balances equal payment-day settled cash, and
that the payment moves from receivable to cash on every later close date.
Illustrative NAV is unchanged on all 1,000 rows because the dividend was
already counted on its ex-date. The new close is still
`PROVISIONAL_UNAPPROVED`: 143 other action events await review, most dates
have no bank statement, and borrow fees and tax are absent. This pilot did
not create a publishable two-year NAV series.

## Reviewed and pending dividend views of NAV

The payment-aware close above still includes all 143 unreviewed provider
events in its `illustrative_nav_usd`. To see their effect without treating
them as accepted accounting entries, run:

```powershell
.\.venv\dbt\Scripts\python.exe scripts\build_two_year_close.py --config config\two_year_replay_v2.json --apply-dividend-pilot --separate-pending-dividends
```

The new `data/two_year_close/provisional_v2_review_split/daily.csv` keeps the
old illustrative figure and adds `nav_excluding_pending_actions_usd` and
`pending_candidate_impact_usd`. It also splits dividend receivables and
short-dividend payables into reviewed and pending balances. These are two
views of the **same** trades, prices, cash and Mastercard payment:

```text
illustrative NAV = NAV excluding pending actions + pending candidate impact
```

On September 21, 2026, the pending impact is about **-$6,597.82** for account
01 and **-$467.88** for account 02. Removing those pending amounts raises the
comparison NAV to $4,715,682.24 and $4,815,732.39 respectively. The negative
impact reflects possible dividend payments owed on short shares as well as
possible receipts on long shares; it is not a loss newly created by this
calculation. The CSV retains the unrounded decimal results for audit.

The builder checks all 1,000 rows against the earlier payment-aware close:
every old field is unchanged, reviewed plus pending balances equal the old
total, and the two NAV figures differ by exactly the pending impact. It
also checks the review queue against the approved-action seed: one reviewed
event and 143 pending event IDs. **Neither NAV figure is approved for
publication.** Other accounting and bank evidence gaps remain.

## Which pending action to review first

Run `scripts/prepare_two_year_action_review_queue.py` to rank the 143 pending
dividends against the saved account-level entitlements. The output is
`data/two_year_action_review/v1/queue.csv`, with hashes of its inputs in the
adjacent manifest. It ranks by the sum of the absolute amounts across both
accounts: a possible receipt and a possible payment must not cancel each
other when deciding what to investigate first. This sum is review exposure
across events, not a current NAV balance.

The top event is the 19 May 2026 CVX dividend. The review and conditional NAV
impact are recorded in [the CVX review note](action_reviews/cvx_2026-05-19.md).
Its decision is **HOLD_FOR_REVIEW**; the approved-action seed is unchanged.

The decision is also recorded as JSON so a command can check it and calculate
the affected NAV rows:

```powershell
.\.venv\dbt\Scripts\python.exe scripts\preview_two_year_action_decision.py --decision docs\action_reviews\cvx_2026-05-19.json
```

The command checks hashes of the queue, approved-action seed and saved close.
For a hold, `decision_nav_usd` stays at the reviewed-only value;
`nav_if_approved_usd` shows the conditional change. A later approval needs a
new decision ID, a named reviewer, and evidence for the issuer event, ex-date,
security identity and account eligibility. Even an `APPROVE` preview remains
`PREVIEW_ONLY_NOT_PUBLISHED`; moving an approved event into the accounting
close is a separate controlled step. The script does not authenticate the
reviewer or verify that a supplied evidence link supports the decision.

## Apply a reviewed decision to a versioned close

`scripts/apply_two_year_action_decision.py --decision <decision.json>` reads
the same hashed queue and close. A `HOLD` writes no close; running it against
the current CVX decision confirms this. An `APPROVE` creates a new folder under
`data/two_year_close/review_decisions/<decision_id>/`, leaving the original
close in place. The folder contains all daily rows, the entitlement rows,
the dates and accounts whose reviewed NAV changed, and a manifest with source
hashes. It subtracts the selected event from pending receivables/payables and
adds it to reviewed receivables/payables from the ex-date onward. Cash,
positions, market prices and illustrative NAV do not change. The output remains
`PROVISIONAL_UNAPPROVED`: approval of one action cannot resolve the other
pending actions or missing payment and cash evidence.

The approved branch is exercised only with a small fictional test dividend.
Its short account moves from $100 to $90 reviewed NAV, and its long account
from $100 to $108 on the ex-date; both still have the same illustrative NAV.
No real provider event was approved as part of this test. A real approval
requires a new decision record with an accountable reviewer and verified
evidence before running the command.

The command applies one decision to the original saved close. Separate
approval outputs are not cumulative. Use the combined ledger below to apply
several reviewed decisions to one close.

## Combined decision ledger

`docs/action_reviews/decision_ledger.json` lists the decisions in one review
version. Run:

```powershell
.\.venv\dbt\Scripts\python.exe scripts\apply_two_year_action_ledger.py
```

The command reads each decision against the saved queue and close. It rejects
two decisions for the same event or the same decision ID, applies approvals in
a fixed order, and writes one new close under
`data/two_year_close/review_ledgers/<ledger_id>/`. The manifest records the
ledger, each decision hash, and the source close hash. Use a new ledger ID for
a later set of decisions; the earlier version remains available for audit.

Ledger `TWO_YEAR_REVIEW_001` contains only the real CVX HOLD. It
produced zero NAV differences: its 1,000 daily rows and 288 entitlements have
the same hashes as the starting close. A fictional test applies two approved
dividends and a held dividend together. The two approvals add to reviewed NAV
once each, the held amount stays pending, and reversing the input order gives
the same result. No real provider dividend was newly approved in that test.
The combined output is still provisional; this ledger does not verify payment
or make the result publishable.

A later `TWO_YEAR_REVIEW_003` ledger includes two Chevron holds and one
project-owner-approved PepsiCo entitlement. It moves that candidate from
pending to reviewed on 396 account-day rows without changing cash or
illustrative NAV. See [the PepsiCo review](action_reviews/pep_2025-12-05.md).
The later ledger has 142 pending dividend events and remains provisional.

For exploratory exposure analysis, `scripts/build_two_year_reporting.py`
turns the ledger close into account-day and position-day CSVs. See
[the reporting extract guide](two_year_reporting.md) for their keys, checks,
and limits.

The pending dividend queue now has a separate issuer comparison report. See
[the issuer triage guide](dividend_issuer_triage.md) for its evidence, conflicts,
and coverage. This comparison does not approve any dividend or publish NAV.
