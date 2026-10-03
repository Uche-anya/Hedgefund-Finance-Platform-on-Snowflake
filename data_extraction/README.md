# Data extraction

## Replay instrument inspection

The active price snapshot has no stable identifiers for its 20 replay stocks.
Collect dated Massive reference evidence before building `dim_instrument`:

```powershell
python -m data_extraction.inspect_replay_instruments
```

The command asks for the Massive key without displaying it, spaces the 20 API
requests using the existing reference helper, and saves every raw response under
`data/instrument_reference`. It checks CIK, composite FIGI, share-class FIGI,
security type, exchange, currency and active status. The resulting status is
pending manual approval; it does not alter prices or create a Snowflake mapping.

The September 2026 universe file identifies the new Exxon holding company, while
the January 2025 reference record identifies the predecessor. Save the two sides
of the July 2026 transition before defining XOM's effective-dated mapping:

```powershell
python -m data_extraction.check_xom_transition
```

Run these commands from the project root. `-m` runs a Python module in this
folder and lets the scripts import their shared functions.

| Scripts | Purpose |
| --- | --- |
| historical_prices.py | Download daily bars and resume interrupted downloads |
| check_*identity.py, check_*identities.py, check_ticker_changes.py | Save dated security reference evidence |
| repair_*.py | Build the reviewed ticker histories |
| assemble_prices.py | Combine the saved snapshot and approved repairs |
| market_prices.py, fx_rates.py | Earlier EODHD sample and ECB FX downloaders |

Examples:

```powershell
python -m data_extraction.historical_prices --help
python -m data_extraction.historical_prices --resume "data/historical_prices/YOUR_FOLDER_ID"
python -m data_extraction.check_merger_identities
python -m data_extraction.repair_merger_histories
python -m data_extraction.assemble_prices
```

Downloads and repairs prompt for the Massive key when needed. Assembly uses
saved files and needs no key. The existing data/ and config/ locations are
unchanged. Running assembly again creates a new output folder; moving the
scripts does not require downloading or assembling the existing data again.

Corporate actions: see [download instructions](../docs/corporate_actions.md) for splits and dividends.
