# Download corporate actions

Run from the project root:

```powershell
python -m data_extraction.corporate_actions
```

Enter the Massive key at the hidden terminal prompt. MASSIVE_API_KEY can also
supply it. The script does not save the key. No live download has been verified
yet: the key was unavailable in the development session.

The script requests market-wide pages from the current
[split endpoint](https://massive.com/docs/rest/stocks/corporate-actions/splits)
and [dividend endpoint](https://massive.com/docs/rest/stocks/corporate-actions/dividends).
It follows pagination at a conservative request rate, then selects candidate
records using every source ticker in our assembled price snapshot, including
historical symbols. This avoids two separate requests for each stock.

Outputs are under `data/corporate_actions/<id>/`:

- `request.json`: date range, candidate symbols and price-file hash.
- `splits_0001.json`, `dividends_0001.json`, etc.: provider response fields,
  reserialised with credentials removed from pagination URLs.
- `splits.jsonl`, `dividends.jsonl`: candidate events and source-row references.
- `manifest.json`: page hashes, retrieval times, counts and completion status.

The command prints a resume command. Rerunning with that folder verifies saved
pages and fetches the remaining ones. Empty event lists are valid; HTTP errors
are not treated as zero events. The status stays INCOMPLETE on a failed first run.

Free-tier history is rolling. By default the start is one day inside the two-year
anniversary, or the price start if later; the end is the saved price end. The
exact coverage is printed and recorded. `--start YYYY-MM-DD` allows an explicit
range if the account can access it. No silent retry with a shorter date range.

Ticker matches require identity review, especially reused symbols. These files
are not ready-to-apply accounting adjustments. Dividend selection uses ex-date;
this is not a payment-date report. Use original cash_amount for dated holdings,
not split_adjusted_cash_amount. Today's historical records also do not establish
what was known at each historical reporting cutoff. Snowflake loading and
holdings/cash adjustments are separate next steps.

## BNY dividend review, September 27, 2026

Ran `python -m data_extraction.review_bny_dividends`. It verified the saved
reference JSON fingerprints and bank/fund identifiers using the existing BNY
identity checks, then recorded 17 pre-change BNY dividends as EXCLUDED_FROM_BANK.
Their ex-dates span October 15, 2024 through February 6, 2026. The bank used BK
before May 21, 2026. Eight remaining BK/BNY dividend candidates remain NEEDS_REVIEW;
no entitlement or payment has been approved automatically.

The separate decision CSV and evidence manifest are in
`data/corporate_action_reviews/0a2042dd095e4a348a1dd75064a87658/`.
Original downloads remain intact. These decisions are not yet consumed by a
Snowflake model. Future staging must apply exclusions by snapshot and event ID,
not delete source records or globally drop the BNY ticker.

Evidence: the four saved dated Massive reference responses, the bank's
[ticker-change announcement](https://www.bny.com/corporate/global/en/about-us/newsroom/press-release/bny-announces-planned-change-of-stock-ticker-symbol-to-bny-130465.html),
and the [BlackRock distribution notice](https://www.blackrock.com/us/individual/literature/press-release/1-2-26-pr-muni-div-release.pdf).
This supports exclusion from bank calculations; it does not independently
certify every historical BlackRock dividend amount.

## Review of apparent dividend duplicates

The September 27 review found ten pairs (20 events) sharing ticker, ex-date,
amount and currency. `python -m data_extraction.review_dividend_pairs` preserves
both source records and writes decisions by event ID into a new review folder.
The first result is `data/corporate_action_reviews/26e32fc523e24ab08a0c479c0369e423/`.

- Eight FCX pairs are separate base/variable components, USD 0.075 each. The
  issuer's dividend history lists both on all eight matching record/payment dates.
- Ford's February 2025 pair is regular plus supplemental, USD 0.15 each. The
  filing supports both amounts and the exchange notice confirms supplemental
  dates. Differing provider declaration dates remain uncorrected.
- TEL's November 2024 pair remains HOLD_FOR_REVIEW. The issuer describes a
  single USD 0.65 installment; provider IDs and adjustment factors differ.
  Neither row was chosen as canonical. Do not sum the pair or silently omit
  the entitlement when building an account calculation; block it for resolution.

The 18 KEEP_SEPARATE_COMPONENTS decisions resolve only duplicate suspicion.
They do not approve account eligibility or all source fields. No Snowflake
transformation consumes these decisions yet. Source URLs are saved in the CSV.

## TEL cash-event resolution

`python -m data_extraction.resolve_tel_dividend` produces one reviewed USD 0.65
cash event linked to both original TEL records. The exact pair agrees on all
fields except provider ID and historical adjustment factor. The issuer's
September 30, 2024 announcement supports one installment for the November 22
record date, payable December 6. Ex-date remains sourced from the agreeing
provider records. Incorporation change is not a proven explanation for duplicate
provider records.

Output: `data/corporate_action_reviews/33fbc11bbd4740e5905b49cbcc3060b4/tel_reviewed_event.json`.
The adjustment factor is deliberately null in the reviewed event; both conflicting
values remain in its source records. This supersedes the prior TEL cash-duplication
hold only. Future transformations must replace both exact source IDs with this
single reviewed event, not append it alongside them. The original download is
unchanged; no Snowflake model has applied this resolution yet. Eligibility,
security identity and payment confirmation are still separate requirements.

## Loaded into Snowflake

September 27, 2026: SQL 19 provisioned the raw tables and SQL 20 loaded the
verified candidates and review history. Both COPY statements reported zero
errors. Actions: 3,247 dividends and 24 split-related records, with matching
unique event-ID counts. Reviews: 25 BNY decisions, 20 paired-event decisions,
and one TEL resolution (46 records total).

Tables:
- `NORTHBRIDGE_DEV.RAW.CORPORATE_ACTIONS`
- `NORTHBRIDGE_DEV.RAW.CORPORATE_ACTION_REVIEWS`

Load ID: `890be0cfdcf2151ebb4aab47f0d53cd9`.
Snapshot: `7962b1659329451b86a5eb288fd7d61e`.
Execution record: `data/admin_runs/c6bb3c1274464e3992f4a6dc2c124f9b.json`.

`python scripts/prepare_corporate_actions_load.py` verifies input fingerprints,
packages records with their provenance, and generates SQL 20. SQL 19 is setup;
SQL 20 uploads and copies the pinned load. One reusable stage holds both files
under a load-specific path. Normal COPY retries use FORCE=FALSE. Different load
IDs may contain the same source events, so future staging must select its load
explicitly rather than blindly union every delivery.

Raw actions retain the original candidates, including excluded BNY records and
both TEL records. Review history retains the old TEL hold alongside its later
resolution; dbt must interpret supersession before applying it. Recorded review
manifests describe their historical local state, not current ingestion status.
No holdings, cash or NAV models have been changed. The market-wide response
pages remain local; Snowflake contains our 3,271 candidate records.

## One dbt staging view

`NORTHBRIDGE_DEV.DBT_DEV.STG_CORPORATE_ACTIONS` built successfully with three
focused tests on September 27, 2026. Run:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select "stg_corporate_actions corporate_actions_review_coverage"
```

The model reads the pinned corporate_action_load_id. CTEs (named steps within
one SQL query) unpack review records and construct the reviewed TEL replacement.
No separate review model, split model or dividend model was added.

Output is 3,253 rows: 3,271 raw candidates minus 17 bank-universe exclusions,
minus two original TEL events plus one reviewed TEL event. The 18 FCX/Ford
components remain separate. This view is scoped to our equity universe, not a
universal corporate-action master: the BlackRock fund events remain in RAW.

The three tests check event uniqueness, required typed fields and values, and
source-ID coverage with the pinned review outcomes. Decimal amounts allow up to
12 fractional places and 26 integer digits; the model rejects excess precision
before conversion rather than silently rounding it.
Missing declaration dates are preserved, not invented. Source payloads and
review evidence remain available, including the original conflicting TEL factors.

Review_decision states what was decided about the source record. Accounting_status
explicitly leaves security identity and account eligibility unapproved. Do not
interpret KEEP_SEPARATE_COMPONENTS or ONE_CASH_ENTITLEMENT as approval to pay cash.
Future work must handle special distributions, reverse splits, stock dividends,
missing reference data and point-in-time eligibility before valuation changes.
New/changed review rules require a new reviewed load and corresponding tests;
this model is not a general workflow for arbitrary decision supersession.

Inspect the result:

```sql
SELECT event_id, action_type, ticker, ex_dividend_date, execution_date,
       cash_amount, currency, split_from, split_to, review_decision
FROM NORTHBRIDGE_DEV.DBT_DEV.STG_CORPORATE_ACTIONS
ORDER BY ticker, ex_dividend_date, execution_date;
```


### Independent correctness review

Rebuilt the view and reran its three tests after rejecting excess numeric
precision in the model. `scripts/check_corporate_actions.py` independently
reconstructs expected events from fingerprint-verified local downloads and review
files. It matched all 3,253 Snowflake rows, their typed fields, review decisions
and source-ID lists exactly. A SQL edge-case check confirmed that a value with
13 fractional digits is rejected.

This validates the pinned snapshot. It does not certify the underlying provider
facts or implement a general policy for future conflicting review decisions.
Additional review versions can multiply joins; uniqueness tests detect visible
duplicates, but new decision histories need explicit policy review before use.
