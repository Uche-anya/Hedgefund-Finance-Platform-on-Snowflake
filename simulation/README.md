# Simulated fund activity

The current two-year v2 scenario produces fictional OMS executions and
custodian settlement confirmations. Five dated deliveries per feed were loaded
through Snowpipe; the remaining historical dates were loaded in bulk.
See [the two-year Snowflake path](../docs/two_year_snowflake_path.md).

`daily_oms.py` and `daily_settlements.py` produce the two-year fund events and
new daily deliveries. `simulator.py` supplies execution validation shared by
those producers. `pilot_opening.py` creates the opening subscription evidence.

Every produced fund event is fictional and should retain its scenario ID and
simulation flag when loaded to Snowflake.
