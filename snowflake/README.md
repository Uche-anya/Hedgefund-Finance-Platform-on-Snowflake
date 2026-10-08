# Snowflake SQL

This folder holds SQL still useful for the two-year development pipeline. It is
not a migration runner: do not execute every numbered file in sequence. Some
files create objects, some load a fixed saved delivery, and some only inspect
results.

| Files | Use |
| --- | --- |
| `01`, `06` | Development database and dbt role setup |
| `12`-`14`, `16`, `19`, `20`, `28` | Current RAW tables, stages and saved backfill loads |
| `34`, `38`, `48`, `49`, `58` | Snowpipes, delivery receipts, payment storage and daily price-loader grant |
| `50`, `51` | Saved two-year close comparison data and checks |
| `29`, `30`, `35`, `47`, `52`, `53`, `57`, `59` | Cost, governance, ingestion and close checks |
| `60`, `61` | Close-input control tables and read-only 22 September source audit; run in development |
| `62` | Development close attempt and versioned result tables; run in development |
| `63` | Selected-input audit, build gate and single-writer lock for the development close |
| `64` | One direct Snowflake-native dbt build of the pinned corrected candidate |
| `65`, `66` | Unscheduled pilot Task graph and manual execution |
| `67` | Task run ownership, result capture and failure cleanup procedures; apply before `65` |
| `68` | DEV-only failure drill; restore `65` after its Task run finishes |

The fixed load files (`13` and `20`) reproduce particular historical deliveries;
they are not daily ingestion jobs. The current daily path uses the
Snowpipes in `34` and `48` and the Python daily price loader. The pilot root
Task is suspended and has no schedule. Its steps claim the close, run dbt,
capture or compare the versioned result, and clear ownership. A finalizer marks
a failed run and releases ownership. Run `scripts/check_close_pilot_task.py` to
inspect the latest run. This fixed-request pilot does not publish NAV.

Terraform manages durable CI and production account objects.

`07` and `27` are machine-generated dbt and ingestion access SQL. They are
ignored by Git and may be regenerated when a service key is rotated. Private
keys stay outside the repository.

`NORTHBRIDGE_PROD` currently has only its Terraform-managed foundation. Before
enabling production deployment or a daily task, the current RAW objects need
ordered, environment-aware migrations and a production dry run. See
[the roadmap](../docs/ROADMAP.md).
