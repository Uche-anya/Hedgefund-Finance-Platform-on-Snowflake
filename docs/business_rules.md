# Rules for part 1

[Part 22](lesson_22_exchange_calendar.md) adds an optional sourced January 2025
calendar selected by path and fingerprint. It must cover every date in its range;
opening and valuation dates must be consecutive open dates. Calendar evidence is
frozen with the candidate and its hash participates in reuse. Old configurations
retain the weekday-only rule. The real 9 January 2025 closure is included; earlier
9 January examples remain explicitly simulated. Payment confirmation and due-date
rules remain separate from valuation-day selection.

Current daily calendar update: [Part 21](lesson_21_weekday_calendar.md) replaces the
earlier consecutive-calendar-day restriction with consecutive Monday-Friday closes.
No holidays are excluded yet. Settlements of carried obligations must fall after
the opening close and on/before the new close; new trades cannot settle before
their trade date. Due dates are not shifted automatically, and missing current-date
prices or reference deliveries stop processing.

[Part 15](lesson_15_daily_cash.md) adds a separate daily cash calculation: carry
local-currency settled cash and detailed open obligations, create today's trade
obligations, and remove them only with matching full same-day confirmations.
Exact repeated settlement rows count once; confirmations without an open obligation
fail. Opening obligation totals must reconcile and new executions must not reuse
known IDs. Daily NAV and publication integration remain pending.

For the separate next-day holdings lesson, see
[Part 14](lesson_14_opening_holdings.md). It adds today's allocated trade changes
to the previous calendar day's latest published quantities, preserving portfolio
and instrument keys. It does not yet extend cash, settlement or NAV to a second day.

These rules describe a small educational valuation fixture, not complete fund
accounting. Read these before changing the calculation.

- One fictional fund, two portfolios, GBP cash and GBP equity prices.
- Positions and cash are supplied opening balances, already settled. The
  calculation does not derive them from a trading system yet.
- Each position row means one portfolio's signed share quantity in one
  instrument on one business date. Each price row means one instrument's
  approved, unadjusted closing price for that date. Approval is an assumption
  of this curated fixture, not an implemented workflow.
- Prices are GBP per share, not pence. All input dates must match the requested
  business date. There is no stale-price fallback. Market calendars and actual
  source arrival cut-offs remain to be designed.
- Long quantities are positive, short quantities negative. Market value equals
  signed quantity times price. Do not subtract the short obligation a second time.
- Cash is one GBP balance for the fund. Short-sale proceeds are already included.
  We do not calculate available buying power, collateral or restricted cash.
- NAV equals cash plus all signed equity market values in this fixture.
  Other receivables, liabilities, borrow costs, fees and taxes are absent.
- No intraday activity, unsettled trades, corporate actions or investor flows.
  No FX conversion is implemented. Non-GBP records are rejected.
- Use decimal arithmetic. Keep full precision during calculation; round only
  final displayed GBP amounts to pennies, using ROUND_HALF_UP.
- Reject duplicate business keys, missing prices, non-finite numbers and prices
  that are zero or negative. A failure stops this local calculation. There is
  no publication system yet.
- Values can be added across these disjoint holdings for this date. Daily NAV
  snapshots must not be added across dates; prices must not be summed.

## Later rules, not implemented

Use weighted-average cost with separate long/short handling when trades are
introduced. Specify trade-date obligations separately from settled cash.
Work through partial closes, crossing zero, FX, fees, splits, dividends and
subscriptions/redemptions by hand before implementing them.

The present fixture's expected NAV is independently worked out in the README.
Tests use that fixed expected answer, not a second call to the calculation.

## Part 3: quantity-only trade scenario

- Separate synthetic scenario starting from zero holdings for every portfolio.
  It is not additional trading applied to the Part 1 opening positions or cash.
- Each execution row is one completed trade from one simulated source.
  Execution IDs are unique within that source; allocations have their own IDs.
- Each allocation links one execution to one portfolio. All allocations for
  an execution must sum exactly to its executed quantity. Splits are supported.
- Source quantities are finite positive decimals; BUY adds and SELL subtracts.
  Final positions have grain portfolio + instrument for the selected date.
- All records must describe the requested business date. Empty files with the
  correct headers represent no activity; this lesson starts from zero holdings.
- Exact repeated records with the same ID are counted once and reported.
  Conflicting repetitions fail. No source revisions or cancellation rules yet.
- Rebuild the entire selected delivery each time; there is no persistent event
  state, cross-date position roll-forward or resolution across deliveries.
- This step calculates only share quantities. Execution prices, order linkage,
  borrowing checks, cost basis and cash/settlement are still to be implemented.
  Do not use these quantities with Part 1's cash balance to claim a valid NAV.

## Part 4: cash and settlement

- A separate complete scenario repeats Part 3's trades, with GBP 10,000 opening
  settled cash immediately before those trades and zero opening obligations.
- Execution prices are GBP per share: E001 buys 100 at 10; E002 sells 30 at 11;
  E003 shorts 20 at 20. No fees, FX, taxes, interest or collateral movements.
- Recognise positions and trade receivables/payables on the trade date.
  BUY creates a payable; SELL (including a short sale) creates a receivable.
- Cash changes only when an explicit full-settlement confirmation has an actual
  settlement date on or before the requested as-of date. A due date alone never
  proves settlement. Unconfirmed overdue trades retain their obligations.
- Settlement removes the obligation and moves the same amount into settled cash.
  Cash + receivables - payables therefore stays constant when only settlement
  changes. Short-sale proceeds are accounting cash, not necessarily spendable.
- Full settlement amount must equal executed quantity times execution price,
  with positive amount and matching GBP currency. Reject partial settlements,
  multiple distinct confirmations per execution, unknown references, invalid
  dates and amounts, and conflicting IDs. Exact repeats count once.
- Cash is calculated once per execution at fund level, not once per allocation.
  Allocation checks from Part 3 must pass first.
- Keep Decimal precision. This lesson accepts only trade totals in whole pennies;
  reject finer totals until an explicit cash rounding/residual rule is designed.
- The delivery contains one trade date and a complete synthetic settlement
  history. As-of dates show end-of-day economic state using that history, not
  what an operator knew at the time. Receipt-time history is not implemented.
- Dates are explicit fixture assumptions; no exchange settlement calendar or
  automatic settlement-lag rule is implemented. Rebuild from the same opening
  cash each time. Do not use a previous closing balance as opening cash here.
- Orders, cost basis, realised P&L, publication and a trade-derived NAV report
  remain pending. The example contains no additional activity after trade date.

## Part 5: NAV from trades, cash and dated prices

- Use Part 4's complete trade batch and settlement history. Derive positions
  and cash through the existing controls, without a supplied positions balance.
- The NAV bundle adds closing_prices.csv, with one row per valuation date and
  instrument. Prices are synthetic GBP per share, assumed approved for the
  exercise. An actual price approval workflow is not implemented.
- Every nonzero position requires a positive finite closing price for exactly
  the requested as-of date. Never use another day's price as a fallback. Reject
  duplicate date/instrument keys, including identical price rows. Zero holdings
  have zero market value and do not require a price.
- Signed market value = quantity times closing price. Positive values are long
  assets; the absolute values of negative positions are short obligations.
- NAV = settled cash + receivables - payables + long assets - short obligations.
  Short-sale proceeds are already included in cash or receivables. Subtract each
  short obligation once, not again as another separate liability.
- Keep full Decimal precision and round only displayed GBP amounts to pennies.
- The fixture explicitly supplies unchanged prices for 14, 15 and 16 September
  to isolate settlement effects. These are separate dated observations, not
  forward-filled market data. With unchanged prices and quantities, settlement
  alone must leave NAV unchanged.
- Overdue obligations remain included and are shown in the report. All results
  are NOT APPROVED; no reconciliation, publication, performance return or
  realised/unrealised P&L calculation is claimed by this lesson.

## Part 6: independent fixture reconciliation

- One fictional fund, NORTHBRIDGE, with hand-worked synthetic reference files.
  Reference values are authored separately, never generated by calculate_nav().
- Compare broker positions at portfolio + instrument, on a TRADE_DATE basis;
  broker cash is SETTLED fund-level GBP cash. Compare administrator NAV for the
  same fund, GBP and as-of date. The initial reference files cover 16 September.
- Require unique keys on both sides and compare their union. Missing records
  fail; missing values are not silently replaced with zero. Even an explicit
  zero on only one side requires investigation under this strict initial rule.
- Difference = our value minus reference value. Position tolerance is exactly
  zero shares; cash and NAV tolerance is GBP 0.01 inclusive, before rounding.
  These are educational fixture thresholds, not agreed production materiality.
- Wrong dates, bases, fund, currencies, malformed values or duplicate reference
  keys stop reconciliation. A broken input/calculation cannot yield PASS.
- Every report identifies its run and both input deliveries. Each control gives
  its entity, date, unit, expected/reference, actual/internal, difference,
  tolerance, status and reason. Failure gives a nonzero command exit status.
- PASS means these comparisons matched, not approval to publish. No publication
  system exists yet. Synthetic counterparties do not prove real-world correctness.

## Part 7: local approval and publication

- Store an immutable candidate containing the close and the reconciliation that
  checked that exact close. Approval never means recalculating different inputs.
- A candidate is eligible only if reconciliation and every control passed and
  there are no overdue trade obligations. Publication also requires a separately
  recorded nonblank reviewer name, review note and approval timestamp.
- This local reviewer name is an asserted identity, not an authenticated user.
  The lesson demonstrates the workflow; it does not implement access control.
- Approval records the current published version the reviewer expects (0 means
  none). If another candidate is published first, the stale approval cannot
  replace it. Prepare and review a new candidate against the latest version.
- SQLite transactions assign one successive version per fund valuation date.
  A publication inserts its complete candidate reference in one transaction.
  Consumers read the highest committed version for that date. There is no
  partially updated mix of cash, holdings and NAV exposed to readers.
- Candidate, approval and publication rows cannot be updated or deleted through
  the database's ordinary statements: triggers reject those operations. This is
  local accidental-change protection, not tamper-proof or cloud-secured storage.
- Republishing an already published candidate returns its original version and
  never promotes an old version again. Corrections use new deliveries, candidate,
  reconciliation, approval and version. Prior published values remain available.
- All amounts are stored as decimal strings inside the saved JSON close.
  The database is for the one NORTHBRIDGE fund in this lesson. Publication is
  local only, with synthetic inputs; no external audience receives these results.

## Part 8: hybrid historical-price scenario

- Fixed EODHD demo symbols AAPL.US and AMZN.US, dated 6-8 January 2025. Retain
  provider IDs and raw responses; use close, not adjusted_close. Missing required
  dates fail. This is a curated two-security mapping, not a historical security master.
- Treat prices as USD per share. The separate single-currency example starts
  with USD 10,000, buys 10 Apple shares and shorts 5 Amazon shares on 6 January
  at hypothetical fills equal to that day's reported closes. Simulated full
  settlement occurs on 7 January; no actual trades or payments are claimed.
- Assume no fees, corporate actions or additional activity in this short example.
  No execution-quality, borrow-availability or corporate-action checks are claimed.
- Currency must be selected explicitly as USD throughout the existing pipeline;
  defaults remain GBP. Reject mismatched currencies. No implicit conversion or
  mixing of currencies within one publication database is allowed.
- The scenario-specific reference calculator uses initial capital plus long/
  short price changes, independently of calculate_nav(). Comparisons are simulated
  and share market inputs; they do not verify the provider against another source.
- The project remains PRE_TRIAL: processing/storage are local. Public API reads
  are allowed; no Snowflake, AWS, subscriptions or account activation was used.

## Part 9: reporting-currency translation

- Retrieve dated ECB daily USD/EUR and GBP/EUR reference observations for the
  fixed three-day example. Preserve source bytes and credit ECB statistics.
- Derive GBP per USD as GBP per EUR divided by USD per EUR. This is our derived
  rate, not an executed FX price. Use the same-date ECB reference with US closing
  share prices; this is not a synchronised US-close FX valuation convention.
- Validate units, denominator, series, date coverage and uniqueness. Require
  both positive finite legs; no missing/stale-rate fallback. Verify derived
  values against raw observations before use.
- Calculate the rate with Decimal precision 40 and round to 12 decimal places,
  ROUND_HALF_UP. Multiply USD amounts by that rate. Keep monetary precision
  until display; do not round each component before calculating NAV.
- Translate cash, receivables, payables, signed position values and each open
  obligation. Do not alter share quantities or original USD balances. Subtract
  short obligations once. Check converted components equal converted USD NAV.
- Save the local USD close, translated GBP close, rate and FX input lineage in
  a separate NOT APPROVED report. There is no actual FX cash movement or FX P&L
  calculation, and no claim that USD reconciliation approves GBP valuation.
- Part 10 adds GBP NAV and settled-cash comparisons against separately calculated
  synthetic references (USD reference / USD per EUR * GBP per EUR), with GBP 0.01
  tolerance. All USD controls must also pass. Check rate direction against raw
  legs within 0.0000000000005 GBP per USD. Missing FX stops preparation.
- Bind GBP references to the exact USD reference and FX manifests. Freeze both
  currencies, rate/date/source and source fingerprints in each review candidate.
  Corrections need new deliveries, a matching reference and a new approval;
  previously published versions remain unchanged. This is local learning evidence,
  not an external administrator reconciliation.
