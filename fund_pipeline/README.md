# Python comparison calculations

The active daily close is being built in Snowflake and dbt. The modules here
calculate a separate two-year close from saved inputs so we can compare
positions, cash and NAV row by row before using dbt results for reporting.

`two_year_close.py` and `two_year_reporting.py` produce comparison evidence.
`action_restatement.py`, `dividend_reconciliation.py` and
`daily_continuation.py` support the reviewed action and new-day checks. These
modules are not a second production publication path.
