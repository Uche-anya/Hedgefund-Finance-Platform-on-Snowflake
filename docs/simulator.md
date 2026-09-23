# Simulator: five trade events over time

Run from the project folder:

```powershell
python -m simulation.simulator
```

This creates five fictional historical executions on January 6, 2025:

| Order in the demo | Instrument | Side | Shares | Price (USD) |
| --- | --- | --- | ---: | ---: |
| 1 | AAPL.US | BUY | 10 | 244.00 |
| 2 | AMZN.US | SELL | 5 | 227.00 |
| 3 | AAPL.US | BUY | 8 | 244.05 |
| 4 | AMZN.US | BUY | 2 | 226.95 |
| 5 | AAPL.US | SELL | 3 | 244.10 |

All prices are invented, not fetched from a market-data provider.
The first trade appears immediately; the producer waits two seconds between
trades and stops after the fifth. A run takes about eight seconds.

An order is a request to trade. An execution (or fill) records a trade that
happened. We start with a completed fill; there is no matching engine here.
One order can eventually have multiple fills, each with its own execution ID.

The script prints a short progress line and saves each event in its own file
under `data/simulator/` as JSONL:
one JSON object per line. JSON stores named fields and their values.
Generated files are already excluded from Git by the project's `data/` rule.

## Read the event

| Field | Meaning |
| --- | --- |
| event_id | Identity of this message; retain it when retrying delivery |
| execution_id | Identity of the fill; corrections retain this ID |
| order_id | Request that led to the fill |
| execution_version | 1 means the first report of this fill |
| instrument_id | AAPL.US identifies Apple in our internal convention |
| side / quantity / execution_price | Buy 10 shares at USD 244 each |
| settlement_due | Expected settlement date, not confirmation of payment |
| scenario_id / is_simulated | Explicitly identifies this fictional scenario |

Quantity and price are decimal strings to preserve their exact values. The
calculation layer will convert them to decimal numbers.

The three source timestamps describe the historical fill, event and publication.
We deliberately keep them in January 2025. A future replay sender must record its
actual send time separately; subtracting these dates from today's receipt time
would not measure live network delay.

Every run of the script creates **five new fictional fills** with new IDs.
To retry sending a fill, reuse its saved file instead of running the generator
again. This lesson uses fixed business values so we can inspect one record;
it is not yet a realistic distribution of trades across a trading day.

Nothing is sent to Snowflake or a broker. No allocation, cash movement or
holdings update happens yet. This scenario is separate from the existing saved
Snowflake sample and the two-event streaming fixture.

## Validate before saving

`save_event()` now calls `validate_execution()` before creating any output.
An invalid message raises `ValueError` with the field and rule that failed.
Validation checks IDs, BUY/SELL, positive finite decimal strings, timezone-aware
timestamps in source order, and valid dates with settlement not before trading.
It leaves the message values unchanged.

This first validator accepts only simulated USD, active, version-1 execution
reports. Corrections and cancellations need their own rules in a later step.
It does not yet check instrument membership in a security master, exchange
hours, holidays, or the correct settlement cycle. Passing means the message
fits this lesson's format, not that a real broker confirmed a trade.

Run the focused checks:

```powershell
python -m unittest discover -s tests -p test_simulator.py -v
```

To see a deliberately invalid trade rejected without changing the generator:

```powershell
python -c "from simulator import create_execution, validate_execution; event = create_execution(); event['quantity'] = '-10'; validate_execution(event)"
```

The expected last line is:
`ValueError: quantity must be a finite number greater than zero`.

## How the loop works

`produce_trades()` reads the five example trades in order. For each one,
`create_execution()` gives it fresh IDs and historical source timestamps,
then `save_event()` validates and writes it. `time.sleep(2)` pauses between
events. The historical event times also advance by two seconds; they are not
measurements of the actual time spent running the program today.

If validation or saving fails, the run stops. Earlier saved events remain on
disk. This is not yet a resumable sender: running the script again creates a
new set of trades rather than retrying the saved messages.

This is a local event producer, not an end-to-end Snowflake streaming connection.
Later steps add corrections, allocations, realistic daily activity and streaming.
