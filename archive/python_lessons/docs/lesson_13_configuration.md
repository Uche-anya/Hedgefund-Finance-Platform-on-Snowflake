# Part 13: save the instructions for a daily run

A **configuration** is a set of settings a program reads. It lets us choose the
data for a run without changing Python code or typing eight command options.

Run our saved historical example from the project folder:

```powershell
python -m fund_pipeline.run_pipeline --config configs/close_2025-01-08.json
```

Open `configs/close_2025-01-08.json` beside the command. It contains:

| Setting | What it selects |
| --- | --- |
| `business_date` | The original trade batch: 6 January 2025 |
| `as_of` | The valuation date: 8 January 2025 |
| `delivery` | Saved trades, cash activity and share prices |
| `references` | Saved USD broker/admin comparison statements |
| `fx_delivery` | Saved exchange-rate observations |
| `gbp_references` | Saved GBP comparison statement |
| `database` | SQLite file holding candidates and review history |
| `run_root` | Folder where each attempt's JSON record is saved |

The configuration is a list of locations and dates. The **input files** contain
the actual data. The **run** is an attempt to process it. The **candidate** is the
saved financial result. These are four different things.

## Understanding the paths

The configuration lives inside `configs/`. A path beginning `../data/` means
"go up one folder, then into data". Relative paths are resolved from the
configuration's folder, not from wherever your terminal happens to be.
For a different location, an absolute path is also accepted. In JSON, forward
slashes are convenient on Windows; backslashes must be escaped as `\\`.

This example points to the deliveries already saved on this machine. A fresh
checkout needs its own collected deliveries and updated paths.

## What gets checked?

The reader requires all eight fields and rejects unknown names, duplicate fields,
blank paths and invalid dates. Use dates in YYYY-MM-DD form. It rejects a valuation
date earlier than the trade batch. The pipeline then verifies the actual delivery
files and financial controls as before.

Use either `--config` or the explicit date/path options. Mixing them is rejected,
so a command-line date cannot silently override the date in the file.

Invalid configuration returns exit code 2 before a run begins. Missing or corrupt
input deliveries produce a FAILED run record and exit code 1. Successful processing
returns 0. A run record includes the configuration's path, fingerprint and settings,
plus the fully resolved input paths.

## How this works with reruns

Switching from the long command to the configuration does not change the financial
inputs. The pipeline therefore reuses the same successful candidate. Configuration
formatting changes alone also do not force a new candidate. Changes to the dates,
selected delivery manifests or financial code still do.

For a future date, collect and check that day's deliveries, then create a matching
configuration. Merely editing `as_of` cannot create missing prices, trades or
comparison statements. Our rolling daily ledger and automatic collection are
still future work.

A scheduler could eventually call this command after the day's deliveries arrive.
We have not installed a scheduler or enabled automatic approval. This lesson makes
the local historical run easier to repeat and inspect.

Read `fund_pipeline/run_config.py` first: it loads the JSON, checks the settings and resolves
the paths. Then read `main()` in `fund_pipeline/run_pipeline.py` to see how those settings are
passed to the same runner we already built.
