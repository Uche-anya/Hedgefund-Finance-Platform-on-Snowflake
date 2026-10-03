# Daily run control

The raw tables prove which records were loaded. Run control proves which exact
deliveries were selected together for a calculation and what happened during
each attempt.

`snowflake/31_run_control.sql` creates three append-only tables:

| Table | One row means |
|---|---|
| `OPERATIONS.RUNS` | One logical daily run or historical replay |
| `OPERATIONS.RUN_INPUTS` | One source delivery selected by that run |
| `OPERATIONS.RUN_EVENTS` | One lifecycle or step event for one attempt |

`OPERATIONS.CURRENT_RUN_STATUS` is a view. It finds the latest `pipeline` event
for each run and presents a convenient current status. The event history remains
unchanged underneath it.

An exact retry uses the same `run_id`, increments `attempt_number`, and appends
new events. A different delivery or code version produces a different `run_id`.
This distinguishes retrying the same work from calculating a revised result.

`run_mode` is `DAILY` for ordinary production processing and `REPLAY` for a
historical recalculation. `scenario_id` is optional because normal production
data will not belong to a simulated scenario.

The dedicated `NORTHBRIDGE_RUNNER` role can append and read run-control records.
It cannot update or delete them. A service user and the Python controller will
use this role without a password.

## Local controller

`scripts/runner_key.py` creates an encrypted private key and saves its unlock
secret in Windows Credential Manager. Only the public key is registered on the
Snowflake service user `NORTHBRIDGE_RUNNER_LOCAL`.

`scripts/run_control.py` verifies every configured manifest before connecting,
derives a deterministic run ID, registers inputs and records each step. Delivery
IDs are passed to dbt with `--vars`; the saved defaults remain development
fallbacks rather than the controller's source of truth.

The controlled execution uses `config/controlled_replay_february.json`.
It registered eight logical sources and completed two identical attempts under
the same deterministic run ID. Run
`snowflake/33_run_control_check.sql` to inspect its current status, inputs and
complete event sequence.
