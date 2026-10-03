# Trade simulator

## Broker statement

Run `python -m simulation.broker_statement` to create a fictional prime-broker
position delivery for 30 January 2025. It calculates trade-date positions from
the saved execution events and does not read a dbt result. The configuration
injects a wrong quantity, a missing position, an unexpected account position and
one late account statement. Synthetic truth stays in the manifest instead of the
statement records.

From the project root:

```powershell
python -m simulation.simulator
```

This creates five fictional execution events in data/simulator/. It writes
local files. A saved file can be uploaded to the internal stage and loaded by
Snowpipe with `python scripts/load_oms_snowpipe.py <file>`. See
[the simulator lesson](../docs/simulator.md) for the event fields and behaviour.

For four fictional settlement confirmations against the saved historical trades:

```powershell
python -m simulation.settlement_simulator
```

See [the settlement lesson](../docs/settlement_simulator.md) for the deliberately
unconfirmed trade, cash signs and replay behaviour.
