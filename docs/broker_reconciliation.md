# Broker position reconciliation

The internal book and the broker statement are calculated separately. The
internal side comes from `fct_daily_positions`. The broker side comes from a
saved JSONL delivery produced by `simulation.broker_statement`.

The broker sends a share-class FIGI. `stg_broker_positions` resolves that external
identifier through `dim_instrument`; the broker is not expected to know a
Northbridge security ID.

## Reconciliation grain

One row in `fct_position_reconciliation` represents:

```text
statement date + account + security + currency
```

A full outer join preserves records found on only one side. The model records two
separate results:

- `book_status`: matched, quantity mismatch, missing at broker or unexpected at broker;
- `timeliness_status`: on time, late or no broker record.

The 30 January statement produces 41 comparison rows. Three are position
exceptions: AMZN differs by three shares, MSFT is missing from the broker file,
and an unexpected account reports 12 AAPL shares. Nineteen received records for
account 02 are late because that statement was published after the 08:00 UTC
deadline.

The exception labels are stored only in the ignored simulator manifest. dbt does
not read them. `scripts/check_broker_reconciliation.py` compares the completed
Snowflake result with that hidden truth after the build.
