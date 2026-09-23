# Data extraction

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
