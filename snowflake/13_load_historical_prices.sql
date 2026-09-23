-- Fixed, locally verified delivery. Run through the CLI, not Snowsight (PUT is local).
-- Uploads prices.csv, loads RAW, then reports delivery-level checks.
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

PUT 'file://C:/Users/UCHE/Desktop/Hedgefund-Finance-Pipeline-on-Snowflake/data/assembled_prices/fb25ddd9838840488e4c8b971ff7e0ae/prices.csv'
    @NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES_STAGE/fb25ddd9838840488e4c8b971ff7e0ae/
    AUTO_COMPRESS = TRUE
    OVERWRITE = FALSE;

COPY INTO NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES (
    valuation_date, universe_ticker, instrument_id, share_class_figi,
    source_ticker, currency, open_price, high_price, low_price, close_price,
    volume, price_basis, identity_status, source_system, input_file, input_row_number,
    delivery_id, source_file, source_row_number
)
FROM (
    SELECT
        t.$1, t.$2, t.$3, t.$4, t.$5, t.$6, t.$7, t.$8,
        t.$9, t.$10, t.$11, t.$12, t.$13, t.$14, t.$15, t.$16,
        'fb25ddd9838840488e4c8b971ff7e0ae',
        METADATA$FILENAME,
        METADATA$FILE_ROW_NUMBER
    FROM @NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES_STAGE/fb25ddd9838840488e4c8b971ff7e0ae/ t
)
FILES = ('prices.csv.gz')
FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES_CSV')
ON_ERROR = ABORT_STATEMENT
FORCE = FALSE;

-- Expected: 250036 rows, 503 tickers, dates 2024-09-23 through 2026-09-21.
SELECT COUNT(*) AS loaded_rows,
       COUNT(DISTINCT universe_ticker) AS tickers,
       MIN(valuation_date) AS first_date,
       MAX(valuation_date) AS last_date
FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
WHERE delivery_id = 'fb25ddd9838840488e4c8b971ff7e0ae';

-- Expected: 0 duplicate groups.
SELECT COUNT(*) AS duplicate_ticker_dates
FROM (
    SELECT universe_ticker, valuation_date
    FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
    WHERE delivery_id = 'fb25ddd9838840488e4c8b971ff7e0ae'
    GROUP BY universe_ticker, valuation_date
    HAVING COUNT(*) > 1
);

-- Expected: 498 tickers with 500 rows; five shorter histories.
SELECT COUNT(*) AS tickers, price_rows
FROM (
    SELECT universe_ticker, COUNT(*) AS price_rows
    FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
    WHERE delivery_id = 'fb25ddd9838840488e4c8b971ff7e0ae'
    GROUP BY universe_ticker
)
GROUP BY price_rows
ORDER BY price_rows;
