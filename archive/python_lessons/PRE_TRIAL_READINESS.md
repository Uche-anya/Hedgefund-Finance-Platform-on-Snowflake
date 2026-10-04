# Pre-trial readiness

**PRE_TRIAL — LOCAL_ONLY=true; SNOWFLAKE_ENABLED=false.** These state the
project's current mode. The readiness gate is incomplete. Part 8 connects a
public market-data demo API and Part 9 connects ECB reference FX for local
historical learning. No warehouse,
cloud infrastructure or paid account is connected or deployed.

| Requirement | Evidence so far | Status | Remaining work / safe fallback |
| --- | --- | --- | --- |
| Product and architecture | README, docs/design.md | PARTIAL | Agree acceptance criteria and cut-offs; record architecture decisions |
| Seven source designs | Initial matrix plus tested EODHD historical demo adapter | PARTIAL | Production vendor licensing, remaining contracts, revisions and live integrations; synthetic fallbacks |
| Data model and history | Proposed grains in docs/design.md | PARTIAL | ERD, full schemas, cardinality, timestamps and version history |
| Financial rules and controls | docs/business_rules.md, manual GBP example | PARTIAL | Trade/cash/FX/fee/action rules and reconciliation thresholds |
| Executable local foundation | Valuation, landing, positions, settlement, NAV, reconciliation and local publication; fixtures, manifests, tests | PARTIAL | Simulator, installable package, PostgreSQL, persistent source version handling and independent general-purpose reference calculator |
| Cloud blueprint and offline checks | Direction only | PLANNED | Snowflake SQL, dbt, Terraform, Airflow and CI; label warehouse code UNVERIFIED |
| Security, budget and activation | Local-only boundary | PLANNED | Roles/policies, costs, region, deployment, cleanup and trial-exit plan |

## Part 1 checks

Run `python -m unittest discover -s tests -v` to check the hand-worked NAV,
missing prices, duplicate prices, duplicate positions and a mismatched date.
This is valuation validation, not proof of ingestion deduplication or broker
reconciliation. A delivery retry should eventually be safely deduplicated;
the current calculator rejects duplicate input keys.

## Checks requiring authorised Snowflake integration later

- Actual stage loading, data types, SQL execution and dbt builds.
- Reruns, late corrections and recovery using real warehouse behaviour.
- Grants, masking, portfolio row access and denied-access cases.
- Atomic publication and competing run behaviour.
- Query performance, warehouse suspension and actual cost observations.
- Sharing to an authorised separate consumer account, plus revocation.

Dependency compatibility and current official cloud documentation will be
checked as each integration is designed. Local tests cannot validate those
integrations. Trial activation and account use require a later explicit instruction.

## Part 2 evidence: 2026-09-17

TESTED: `python -m unittest discover -s tests -v` ran 10 tests, all passing.
Landing tests cover repeated snapshots, interrupted copying, changed saved files,
preserved originals after a correction, and manifest/date checks. A command-line
delivery was saved and valued twice; both closes returned GBP 10,090. The
correction test expects GBP 10,070 when BETA rises to GBP 19.

See `docs/lesson_02_landing.md` for the walkthrough and limitations. Saved files
are immutable by writer convention, not enforced storage retention. Trade-event
deduplication, published result history, independent broker reconciliation and
live market-data collection remain unimplemented.

## Part 3 evidence

TESTED: `python -m unittest discover -s tests -v` ran 18 tests, all passing.
Eight position tests cover saved-delivery replay, exact execution/allocation
repeats, conflicting IDs, allocations split between portfolios, allocation-total
breaks, unknown execution references, invalid quantities and date/side checks.
The command-line trade delivery was replayed twice; each run produced GROWTH /
ALPHA = 70 shares and HEDGE / BETA = -20 shares, from zero opening holdings.

Exact-repeat handling within a complete delivery is now implemented. Persistent
deduplication across incremental loads and source correction/version resolution
remain pending. This lesson calculates no cash, cost basis, P&L or NAV.
See `docs/lesson_03_positions.md` for the worked example and exercise.

## Part 4 evidence

TESTED: `python -m unittest discover -s tests -v` ran 30 tests, all passing.
Twelve cash/settlement tests cover independently worked balances, missing/late
confirmations, duplicates, split allocations, incorrect/partial amounts, unknown
references, conflicting/multiple confirmations, currencies, dates, prices,
allocation breaks and replay from original opening cash.

A saved settlement delivery ran through the CLI for 14, 15 and 16 September.
Cash was respectively GBP 10,000, GBP 9,000 and GBP 9,730; cash plus receivables
less payables was GBP 9,730 on all three dates. This subtotal excludes equities
and is not NAV. This is synthetic retrospective replay, not a live settlement feed.
See `docs/lesson_04_settlement.md` for assumptions and the late-payment exercise.

## Part 5 evidence

TESTED: `python -m unittest discover -s tests -v` ran 39 tests, all passing.
Nine NAV tests cover hand-worked amounts across settlement dates, missing dates
and prices (without stale-price fallback), duplicate/invalid prices, saved-input
replay after a price change, outstanding payables, duplicate trade events and
upstream allocation failures.

A saved six-file NAV delivery ran through the CLI for 14, 15 and 16 September.
Each report produced GBP 10,105 using unchanged dated prices and positions.
ALPHA long assets were GBP 735 and BETA short obligations GBP 360. The test
changing BETA's 16 September price to GBP 19 expects NAV of GBP 10,085 while
the saved original still produces GBP 10,105. All outputs are NOT APPROVED.
See `docs/lesson_05_nav.md`. Independent reconciliation, live data, persisted
financial outputs and cloud integration remain unimplemented.

## Part 6 evidence

TESTED: `python -m unittest discover -s tests -q` ran 49 tests, all passing.
Ten reconciliation tests cover hand-worked matching references, the 69-share
fault with preserved originals, missing rows on both sides, duplicate keys on
both sides, cash/NAV penny thresholds, incompatible context, invalid values,
empty cash statements, an intentionally dropped trade and CLI reports/exit codes.

The matching CLI run passed all four controls: 70 ALPHA shares, -20 BETA shares,
GBP 9,730 settled cash and GBP 10,105 NAV. Its saved report is
`data/reconciliation/e460b0a7d198442dbb8e85e1022f09ae.json`.
The intentional test-copy run failed only ALPHA: actual 70, reference 69,
difference +1 share. Its labelled report is
`data/reconciliation/ed8dade0c71b40acb8a70adc1ac3eaf4.json`.
Both reports identify their input deliveries and remain NOT APPROVED.

These local files are ignored by Git; recreate them with the lesson commands.
Reference fixtures are manually worked, not produced by the calculation under
test. This is not live third-party validation or a general reference engine.
Approval/publication, structured ingestion-error reports and cloud integration
remain pending. See `docs/lesson_06_reconciliation.md`.

## Part 7 evidence

TESTED: `python -m unittest discover -s tests -q` ran 61 tests, all passing.
Twelve publication tests cover explicit approval, the failed 69-share comparison,
review evidence, correction history, repeated publication, competing approvals,
stale review versions, immutable tables, rollback before commit, frozen values,
overdue settlement and the complete CLI workflow.

A separate synthetic demo database was created at
`data/publication_demo_e496e9ca438a4b3ea9201e7fe1868bb3.sqlite`.
Candidate `9619ab19fff54f218f776191d3da31fc` passed reconciliation and was
approved as `demo-reviewer` with an explicit synthetic-demo note. Version 1
for 16 September contained NAV GBP 10,105. This was not approval in the user's
name or publication to any external service. The normal default database was
not used for this demo. Generated databases are ignored by Git.

Publication transactions and retained history are locally tested. Authentication,
authorisation, backup/restore, multi-host concurrency, real third-party inputs,
cross-date restatement propagation and Snowflake integration remain unverified
or unimplemented. See `docs/lesson_07_publication.md`.

## Part 8 evidence

TESTED: `python -m unittest discover -s tests -q` ran 70 tests, all passing.
Nine new tests cover raw preservation, unadjusted-close selection, malformed/
missing/duplicate dates, invalid ranges and values, tampering, incomplete-response
evidence, bounded retries, USD integration, missing prices and currency isolation.
API test responses are invented and safe to commit; they are not vendor observations.

EXECUTED: two public EODHD demo requests successfully downloaded six observations
for AAPL.US and AMZN.US over 6-8 January 2025. Raw responses, normalised CSV,
request details, times and checksums are at
`data/market/0a35a13d137e4627ace8d7a9d668f3ce/`.
The first sandboxed attempt was blocked by network permissions and preserved an
incomplete-delivery diagnostic; the authorised network-enabled retry succeeded.

The hybrid USD example ran through valuation and all four reconciliation checks.
Saved report: `data/reconciliation/877cfb1e0de34809a3c0a8a1d3c20481.json`.
Its NAV input delivery is `data/landing/2025-01-06/18ae80085f1043789b5d604ee44dc216/`;
references are `data/landing/2025-01-08/213ac7b4b9a84e009ae529b887ce0a0c/`.
The example is NOT APPROVED; no automatic publication was performed.

Provider terms/docs were reviewed for private use and the public demo route;
redistribution and production licensing are not authorised by this exercise.
Downloaded and derived data remain ignored by Git. Public fixtures remain
synthetic. FX, general market calendars, source revision handling, official
price approval, production vendor selection and other live sources are pending.
See `docs/lesson_08_real_prices.md` for commands and limitations.

## Part 9 evidence

TESTED: `python -m unittest discover -s tests -q` ran 80 tests, all passing.
Ten new tests cover cross-rate direction, unchanged raw inputs, all monetary
components before/after settlement, FX-only reporting changes, missing dates
and legs, duplicates, invalid values/units, failed downloads, altered/inverted
rates, display rounding, preserved USD values and the translated NAV equation.

EXECUTED: the public ECB API returned six observations (USD/EUR and GBP/EUR)
for 6-8 January 2025. Raw and derived data plus manifest are preserved in
`data/fx/f5a7a63c62c44150b12ebbfdc7a09203/`.
The GBP reporting command ran against the existing saved USD NAV delivery.
Both currencies and FX lineage are in
`data/reporting/a48f3733716849449726d4eab3096e66.json`.
The report is NOT APPROVED; it is not a currency trade or a publication event.

ECB source/reuse documentation was reviewed and attribution recorded. The
derived cross rate is labelled as our calculation. Part 10 below adds GBP checks
and publication. Mixed-currency ledgers, exchange-calendar policies and FX P&L
remain pending. See `docs/lesson_09_fx.md`.

## Part 10 evidence

TESTED: `python -m unittest discover -s tests -q` ran 88 tests, all passing.
Eight new tests cover GBP publication evidence, synthetic rate correction history,
mismatched reference lineage, failed GBP and USD controls, missing FX/arguments,
and frozen candidates after source changes.

EXECUTED: saved USD and ECB deliveries produced seven passing controls. The
separate GBP reference is saved in
`data/landing/2025-01-08/7b49b33130d44197b9a57f1c4e7d2d0e/`.
Candidate `9e4a8a94388140c092c296fd4f269717` was inspected and published as version 1
for 2025-01-08 in `data/gbp_publication_demo.sqlite`, using `demo-reviewer` and an
explicit learning-demonstration note. Both currencies and FX evidence were read
back through `current`. This is not user approval or a production publication.

Reference arithmetic is separate but shares the USD fixture and ECB source;
it is not independent external validation. Correction tests use synthetic rates,
not claimed revisions to real ECB data. See `docs/lesson_10_gbp_approval.md`.

## Part 11 evidence

TESTED: `python -m unittest discover -s tests -q` ran 94 tests, all passing.
Six runner tests cover saved evidence and unapproved output, distinct reruns,
missing FX, failed financial checks, invalid dates and CLI exit codes.

EXECUTED: `fund_pipeline/run_pipeline.py` completed the saved historical USD/GBP scenario.
Run `ce2096600f764bb4b78156a4859f2020` is READY_FOR_REVIEW; candidate
`bd73e1eaf7f1424f9c5e3cb51d27693b` is in `data/gbp_pipeline.sqlite`.
No approval or publication was performed by the runner.
Intentional missing-FX run `7bf2187cb7d74f7caafc4b8bafb85a8e` failed at
`check_inputs` with exit code 1 and no candidate. Both records are in `data/runs/`.

This is saved-input orchestration, not a scheduled service. Automatic ingestion,
rolling trade history, retry deduplication, interrupted-run recovery and deployed
monitoring remain pending. Run JSON and SQLite are not one atomic transaction.
See `docs/lesson_11_pipeline.md`.

## Part 12 evidence

TESTED: `python -m unittest discover -s tests -q` ran 101 tests, all passing.
Rerun coverage includes unchanged inputs, changed FX/references, changed financial
code, corrupted inputs, simultaneous attempts, missing prior run logs, failed
candidates, database isolation and existing approval/publication records.

EXECUTED: run `51026f9c6be4485282ff330df30c2501` created candidate
`bbafbe134c62433db396a4802c6e34f2` in `data/gbp_pipeline.sqlite`.
Run `2dddf8a7cb424b7f98f7bec84adb86e1` reused that same candidate with unchanged
saved inputs. Both reached READY_FOR_REVIEW; neither approved or published it.
Records are in `data/runs/`.

Successful-candidate deduplication now uses a SQLite transaction and a key covering
dates, currency, full input manifest hashes and calculation/validation code hashes.
Each attempt remains separate. Old candidates are not backfilled into the reuse
table; failed candidates are not reused as successes. Interrupted log resolution,
automatic ingestion and deployed scheduling remain pending. See
`docs/lesson_12_reruns.md`.

## Part 13 evidence

TESTED: `python -m unittest discover -s tests -q` ran 104 tests, all passing.
Configuration tests cover execution from a different working folder, reuse of
the same candidate, saved configuration evidence, invalid/duplicate/unknown fields
and rejection of mixed configuration and command-line settings.

EXECUTED: `python -m fund_pipeline.run_pipeline --config configs/close_2025-01-08.json` produced
run `6a31320449804b4ea7d0d5829ea3681a`, READY_FOR_REVIEW, reusing candidate
`bbafbe134c62433db396a4802c6e34f2` in `data/gbp_pipeline.sqlite`.
No new approval or publication was made. The run record preserves the configuration
settings, fingerprint and resolved input locations. This selects existing local
deliveries; automatic ingestion, rolling daily activity and scheduling remain
pending. See `docs/lesson_13_configuration.md`.

## Part 14 evidence

TESTED: `python -m unittest discover -s tests -q` ran 110 tests, all passing.
Six new cases cover next-day buys/short covering and replay, no-trade carry-forward,
sales through zero, new positions, duplicate events, incomplete allocations,
unpublished openings and skipped dates.

EXECUTED: `fund_pipeline/carry_positions.py` read the published 2025-01-08 demonstration close
and newly landed synthetic 2025-01-09 trades. Closing quantities are 13 AAPL.US
in GROWTH and -3 AMZN.US in HEDGE. Report:
`data/positions/e999512e108849a2892603bf65481033.json`.
It records the opening publication version and trade delivery fingerprint.
This remains a holdings-only, unapproved report. Next-day cash, settlement and
NAV integration are pending. See `docs/lesson_14_opening_holdings.md`.

## Part 15 evidence

TESTED: `python -m unittest discover -s tests -q` ran 117 tests, all passing.
Seven new cases cover duplicate settlement rows, deterministic replay, carried
payables/receivables, overdue obligations, later-day settlement replay rejection,
amount/currency/date mismatches, competing confirmations, execution-ID reuse,
opening-total consistency and using original USD cash from a translated close.

EXECUTED: the published 2025-01-08 demonstration supplied opening USD cash. New
synthetic 2025-01-09 activity left cash of USD 8,248.05 and a payable of USD 720.
The intentionally repeated settlement row was ignored. Report:
`data/cash/43d1932742f049f4ae02ce59f2f84c72.json`.
This is a cash-only, unapproved report; simulated execution prices and early
settlement are labelled. Complete daily ledger persistence, valuation, reconciliation
and publication integration remain pending. See `docs/lesson_15_daily_cash.md`.

## Part 16 evidence

TESTED: `python -m unittest discover -s tests -q` ran 121 tests, all passing.
Four new tests cover hand-calculated NAV and replay, settlement neutrality,
short-price sensitivity, and missing/stale/duplicate/invalid/wrong-currency prices.

EXECUTED: `fund_pipeline/daily_nav.py` combined the published 2025-01-08 opening with synthetic
2025-01-09 activity and clearly labelled teaching prices. The result matched the
hand calculation. Report:
`data/daily_nav/e43c2c54317045138c580a1a40c2c960.json`.
Holdings and cash use one pinned opening publication and the same activity delivery.
The report is NOT RECONCILED OR APPROVED. Next-day GBP translation, independent
reference checks and review/publication integration remain pending. See
`docs/lesson_16_daily_nav.md`.

## Part 17 evidence

TESTED: `python -m unittest discover -s tests -q` ran 126 tests, all passing.
Five new cases cover a passing separate reference, the Apple one-share discrepancy
and eligibility block, independent cash/NAV/missing-obligation failures, incorrect
trade identity despite matching obligation totals, and invalid reference context.

EXECUTED: all seven next-day controls passed against the simulated statements.
Report: `data/daily_reconciliation/3bd32c06567646ffa8d4ff95e65c2f78.json`.
An intentional new Apple-12 reference delivery produced a one-share difference,
FAIL/BLOCKED and exit code 1. Report:
`data/daily_reconciliation/562d1a0dd0734dd4aa300810350ee626.json`.
The original reference delivery was preserved. Neither result was approved or
published. Next-day candidate persistence, review/publication integration and GBP
translation remain pending. See `docs/lesson_17_daily_reconciliation.md`.

## Part 18 evidence

TESTED: `python -m unittest discover -s tests -q` ran 131 tests, all passing.
Five new tests cover daily candidate approval/publication and preserved history,
mismatch blocks at both gates, a following day's reconciled publication and
old-execution rejection, frozen evidence/version history, and currency isolation.
The synthetic third-day test settles the carried payable with unchanged NAV and
uses the prior frozen ledger even with its original activity folder unavailable.

EXECUTED: candidate `9f7224b4648c48e0ad0e40dba1e18d2d` was prepared, inspected,
approved under `demo-reviewer` with a learning-demonstration note, and published
as 2025-01-09 version 1 in `data/daily_usd_demo.sqlite`. Reading `current` confirmed
the USD close, unpaid obligation and four known execution IDs. This is a local
synthetic demonstration, not user approval or a production release.

New daily closes now preserve full execution-ID history and can supply later
openings. GBP translation, configured daily orchestration/reuse, opening-correction
invalidation and deployment remain pending. See `docs/lesson_18_daily_publication.md`.

## Part 19 evidence

TESTED: `python -m unittest discover -s tests -q` ran 138 tests, all passing.
Seven new cases cover retry reuse and separate run records, a republished opening,
failed comparisons/missing inputs, overlapping attempts, changed financial code,
already-published candidates and configuration/CLI execution from another folder.

EXECUTED: `python -m fund_pipeline.run_daily --config configs/daily_usd_2025-01-09.json` ran twice.
Run `8c81974f97e14079b1f6a7c8444b4333` created candidate
`d86a96b8a221448b96f5ea579b9021a8`; run `f757f297b76b4be0b5e48f4a9d568a98` reused it.
Both reached READY_FOR_REVIEW in `data/daily_usd_pipeline.sqlite` without approving
or publishing. Logs are in `data/daily_runs/`.

The daily reuse key includes the exact opening publication, dates, delivery
manifest fingerprints and calculation code. Each attempt still recalculates and
rechecks inputs before reuse. Automatic ingestion/scheduling, downstream correction
invalidation and new-day GBP translation remain pending. See
`docs/lesson_19_daily_runner.md`.

## Part 20 evidence

EXECUTED: `python -m fund_pipeline.run_daily --config configs/daily_usd_2025-01-10.json` produced
run `b8ee62d0df4a44ceb02607c25c36270a` and candidate
`8b6b95dd57f7487994e23cd588005c3b`, READY_FOR_REVIEW.
It uses 9 January published candidate `9f7224b4648c48e0ad0e40dba1e18d2d` as opening.

VERIFIED by reading the frozen candidate: all six comparisons pass; holdings are
unchanged; cash is USD 7,528.05; payables and open obligations are zero; NAV is
USD 10,103.05; one USD 720 settlement movement is present; four execution IDs
remain recorded. The USD 65 NAV increase equals 13 shares times the USD 5 Apple
price increase. Approval and publication are absent.

Only fixture/configuration/documentation files were added. Validation used the
actual end-to-end run and assertions against its saved result; the application
code and last full-suite result (138 passing tests) are unchanged. Inputs are
explicitly simulated. See `docs/lesson_20_new_day.md`.

### Part 20 publication follow-up

EXECUTED on 2026-09-20: inspected candidate `8b6b95dd57f7487994e23cd588005c3b`,
recorded a labelled `demo-reviewer` approval against expected version 0, then
published 2025-01-10 version 1 in `data/daily_usd_pipeline.sqlite`.
The `current` readback confirmed that candidate/version and approval, USD 7,528.05
cash, zero payables/open obligations, USD 10,103.05 NAV and four execution IDs.
This completes the local demonstration's review/publication cycle. No application
code or calculation changed; the stored reconciliation retains its original
pre-approval status while separate approval/publication records show the new state.

## Part 21 evidence

TESTED: `python -m unittest discover -s tests -q` ran 144 tests, all passing.
Six new tests cover Friday-to-Monday and ordinary weekdays, rejected weekend/gap
closes, actual weekend settlement dates/repeats/replay, missing confirmations and
overdue obligations, out-of-window settlements and pre-trade settlement rejection.
Existing duplicate replay and date-error tests were updated to the weekday policy.

EXECUTED: Monday run `309a18957cce464fb0a1a2f0a9517b7c` created candidate
`b25424d1d77f4a0dba6a89e94e94be2e`, READY_FOR_REVIEW, using the published Friday
candidate `8b6b95dd57f7487994e23cd588005c3b`. Six comparisons passed, with unchanged
cash/NAV and no approval or publication. Policy and calendar code hash are recorded.

Failure demonstrations saved under `data/daily_runs/`:
- Missing Monday prices: `595f8112d5264e64b3d46dcd031df4eb`.
- Missing Monday references: `82304eff2284491ab3c8c5a3cfb56549`.
- Stale Friday prices supplied for Monday: `3c0b8ab4e0cb4e33a1b6554083bba681`.

All three failed without candidates. This is a weekday-only teaching calendar;
holidays, cutoffs, weekend trades and historical correction handling remain pending.
See `docs/lesson_21_weekday_calendar.md`.

## Part 22 evidence

TESTED: `python -m unittest discover -s tests -q` ran 150 tests, all passing.
Six new cases cover regular/exceptional closures, out-of-range and skipped open
dates, pinned fingerprints and complete calendar coverage, settlement independence,
configuration selection and version-sensitive candidate reuse/frozen evidence.

SOURCED: January 2025 closure dates were checked against the NYSE calendar release
and Nasdaq alerts ETA2025-1 and ETA2025-4. The project calendar records 31 dated
entries, three source URLs, coverage, review date and version project-v1. Its hash
is db08b35ab122d9d38a9a2cd7928f5ae9be6892a68d9c33147f1121e0c7479581.
The extraordinary 9 January closure is included; earlier simulated examples are
not retroactively relabelled as actual trading sessions.

EXECUTED: calendar-aware run `fe14e375a95f43f48534d083d939c92f` created candidate
`5baf7a2df55b4aa0bf6b9c957901906e`, READY_FOR_REVIEW. Readback verified the complete
calendar snapshot/hash, source list, version and passing controls. No approval
or publication occurred. Missing open-day prices and references still failed
without candidates (runs `abe9e99962bc454eb9cbc3297d455512` and
`cff16e44b3cd403b8539355ef05da485`).

This is a manually sourced, bounded January calendar, not a live exchange feed or
settlement calendar. Full-year coverage, early-close/cutoff handling, automatic
updates and scheduling remain pending. See `docs/lesson_22_exchange_calendar.md`.
