# dbt project

dbt runs locally and sends the model SQL to Snowflake. The same model graph is
used for routine processing and for the saved 23-day acceptance fixture.

## Active scope

Normal dbt commands read `models` and `tests`. The project contains:

- an effective-dated instrument seed, an approved-actions seed and eight staging views;
- ten tables covering accounting, reporting conversion, rate analytics and reconciliation;
- reusable controls for contracts, row preservation and accounting identities;
- fixture checks for the pinned January input and its deliberate exceptions.

See [MODEL_INVENTORY.md](MODEL_INVENTORY.md) for each model's grain and why the
earlier lessons are excluded.

The old sample and OMS lessons are preserved under `archive/dbt_lessons`. dbt
does not parse or rebuild them.

## Authentication

The helper uses the dedicated Snowflake user and encrypted key described in
[KEY_AUTH.md](KEY_AUTH.md). It does not prompt for the Snowflake password.

From the repository root:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py debug
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --exclude tag:fixture
```

The routine command excludes expectations tied to one saved replay. Use `build`,
rather than only `run`, so reusable data controls execute after their models.
The helper disables secondary roles and uses the `NORTHBRIDGE_DBT_DEV` role.

A scheduler supplies the delivery IDs and processing dates for each run through
`--vars`. The values in `dbt_project.yml` are the saved development fixture. For
example:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build `
  --exclude tag:fixture `
  --vars '{"replay_delivery_id":"delivery-from-today"}'
```

To run the complete replay, including key-authenticated ingestion, dbt tests and
both independent Python checks:

```powershell
python scripts/run_replay.py
```

## Current result

The live build contains two seeds and eighteen models. The
instrument-master build produced 920 daily position valuations and 46 account-day
NAV rows. The broker model produces 41 comparison rows and three position
exceptions. Independent Python checks confirm the financial values and the
hidden reconciliation truth separately.

The model and control layout is suitable for scheduled runs. The saved replay
still demonstrates the workflow; scheduling, alerting and deployment-host secret
management remain deployment work.
