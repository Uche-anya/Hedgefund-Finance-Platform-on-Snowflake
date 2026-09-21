
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

-- Expect one CSV (possibly compressed). Do not upload both plain and gzip copies.
LIST @NORTHBRIDGE_DEV.RAW.MARKET_SAMPLE_20250106_08;

COPY INTO NORTHBRIDGE_DEV.RAW.CLOSING_PRICES (
    valuation_date, instrument, currency, close_price, price_basis,
    source_system, delivery_id, source_file, source_row_number
)
FROM (
    SELECT
        t.$1, t.$2, t.$3, t.$4,
        'unadjusted',
        'eodhd_demo',
        '0a35a13d137e4627ace8d7a9d668f3ce',
        METADATA$FILENAME,
        METADATA$FILE_ROW_NUMBER
    FROM @NORTHBRIDGE_DEV.RAW.MARKET_SAMPLE_20250106_08 t
)
FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.MARKET_CSV')
PATTERN = '.*closing_prices[.]csv([.]gz)?'
ON_ERROR = ABORT_STATEMENT
FORCE = FALSE;

-- Expect 6: two instruments on January 6, 7 and 8.
SELECT COUNT(*) AS loaded_rows
FROM NORTHBRIDGE_DEV.RAW.CLOSING_PRICES
WHERE source_system = 'eodhd_demo'
  AND delivery_id = '0a35a13d137e4627ace8d7a9d668f3ce';

-- Our holdings are for January 6; expect just the two matching dated prices.
SELECT valuation_date, instrument, currency, close_price, price_basis
FROM NORTHBRIDGE_DEV.RAW.CLOSING_PRICES
WHERE source_system = 'eodhd_demo'
  AND delivery_id = '0a35a13d137e4627ace8d7a9d668f3ce'
  AND valuation_date = '2025-01-06'
ORDER BY instrument;
