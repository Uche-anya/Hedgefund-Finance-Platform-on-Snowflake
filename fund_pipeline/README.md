# Earlier Python fund pipeline

These modules contain the local learning prototype. They cover trade landing,
positions, cash settlement, NAV, reconciliation, review and publication.

- build_positions, carry_positions: holdings from trades and opening positions.
- cash_settlement, carry_cash: settled cash and amounts still due.
- daily_close, fund_nav, daily_nav, report_gbp: valuation and reporting.
- reconcile, reconcile_daily, reconcile_gbp, gbp_reference: comparisons with references.
- publication, prepare_daily: candidate results, review and publication.
- run_pipeline, run_daily, run_config, business_calendar: execution and date rules.
- landing, build_hybrid: save deliveries and build the earlier sample inputs.

Run from the project root using `python -m fund_pipeline.MODULE`, for example:

```powershell
python -m fund_pipeline.run_daily --help
```

The numbered docs/ lessons contain the full commands. The current Snowflake
transformations are in dbt/. This folder is not a deployed production service.
