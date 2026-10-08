# Project status and production gaps

Reviewed 7 October 2026. The active calculation is the two-year v2 equity
scenario, not the retired January-February short replay.

## Proven in development

- Real historical prices: 250,036 RAW rows for 503 tickers, spanning
  23 September 2024 to 21 September 2026. Corporate-action data and reviewed
  security identities are saved separately.
- Fictional fund activity: OMS and custodian settlement feeds for the two-year
  scenario. Five original daily files per feed plus one new dated file per
  feed were loaded through Snowpipe; 493 older dates per feed used bulk
  `COPY INTO`. The new custodian file confirms the prior day's trades.
- A checked 20-ticker Massive price package was loaded for 22 September 2026.
  Active dbt models now calculate 19,574 dated positions and 1,002
  account-day provisional NAV rows from RAW data. Three parity tests compare
  the original 500 dates with the saved independent Python close.
- The short replay's Snowflake tasks and rebuildable dbt relations were
  removed. RAW deliveries and audit history remain.

## Open before daily operation

1. Deploy an environment-aware RAW migration and the two-year dbt graph to
   production. The Terraform foundation alone is not a running data plane.
2. Replace the laptop-driven files with controlled daily source hand-offs.
   Current internal-stage pipes require explicit notifications.
3. Define source deadlines and a date-scoped delivery-readiness gate, then
   deploy a new scheduled task graph for this scenario.
4. Obtain independent broker and bank evidence and review held corporate
   actions before claiming an approved NAV.
5. Separate reviewer approval from calculation and implement publication,
   monitoring, retry and recovery for the new graph.

The result is a credible engineering demonstration, not a live fund service.
Stock borrow, margin, withholding tax and non-equity assets remain outside
the accounting scope.
