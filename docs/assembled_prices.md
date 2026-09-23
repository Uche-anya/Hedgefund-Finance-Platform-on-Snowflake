# Assembled historical prices

Run `python -m data_extraction.assemble_prices` from the project folder. No API key is needed:
this step reads the saved original snapshot and the eight approved repairs.
Each run writes a new folder under data/assembled_prices; originals stay intact.

## Files

- prices.csv: one row per universe ticker and trading date, with unadjusted
  opening, high, low and closing prices and volume.
- coverage.csv: original and assembled counts, date ranges and repair status
  for each of the 503 tickers.
- manifest.json: date range, count reconciliation, input and output SHA-256
  fingerprints, limitations and the script fingerprint. Written last; a folder
  without it is incomplete.

The snapshot and repair folder IDs are explicit at the top of the script.
It never picks the newest folder automatically. Its scope is this reviewed
September 2026 dataset, not a general daily ingestion job.

## Replacement and checks

BNY, XYZ, ECHO, P, FISV, MRSH, EXE and VMRK use only the corresponding repair
CSV. Their original rows are excluded completely, including BNY's old fund
prices. The other 495 histories use their original JSON bars.

The script verifies saved fingerprints, original manifest counts, repair
provenance, dated ticker mappings, numeric prices, ordering and duplicate dates.
It compares coverage against the saved AAPL sessions. FDXF, HONA, PSKY, Q and
SNDK are checked from their reviewed start dates; no earlier prices are filled.
This remains a peer-date check, not an independent exchange-calendar check.

## Reading the columns

`universe_ticker` groups a history under the downloaded universe's symbol.
`source_ticker` is the symbol under which that particular price was obtained.
For example, an older BNY row has source_ticker BK.

`instrument_id` and `share_class_figi` are populated for the eight repairs.
The remaining histories have blank IDs and identity_status provider_ticker_only.
Do not treat the universe ticker as a permanent security identifier. Even the
reviewed transitions use dated observations, not daily identity verification.

`input_file` and `input_row_number` locate the immediate input. The number is
one-based, excluding the CSV header, or the position in a JSON results array.
Repair manifests lead back to the provider responses and reference evidence.
USD is the scope of this US-stock snapshot; aggregate bars do not independently
verify currency for every unreviewed security.

The universe is snapshot membership, not historical index membership. It has
survivorship bias and should not be presented as a historical index backtest.
Unadjusted prices also need corporate-action handling before calculating
multi-day holdings or returns. This assembly does not load Snowflake.
