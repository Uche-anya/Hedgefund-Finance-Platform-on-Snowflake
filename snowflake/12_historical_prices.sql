-- Run in Snowsight. Prepares storage only; no records are loaded.
-- Live execution has not been verified.
USE ROLE SYSADMIN;

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES (
    valuation_date VARCHAR,
    universe_ticker VARCHAR,
    instrument_id VARCHAR,
    share_class_figi VARCHAR,
    source_ticker VARCHAR,
    currency VARCHAR,
    open_price VARCHAR,
    high_price VARCHAR,
    low_price VARCHAR,
    close_price VARCHAR,
    volume VARCHAR,
    price_basis VARCHAR,
    identity_status VARCHAR,
    source_system VARCHAR,
    input_file VARCHAR,
    input_row_number VARCHAR,
    -- The local input reference above differs from the uploaded Snowflake file.
    delivery_id VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    source_row_number NUMBER(38, 0) NOT NULL,
    loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP() NOT NULL
);

CREATE FILE FORMAT IF NOT EXISTS NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES_CSV
    TYPE = CSV
    SKIP_HEADER = 1
    FIELD_OPTIONALLY_ENCLOSED_BY = '"'
    ESCAPE_UNENCLOSED_FIELD = NONE
    EMPTY_FIELD_AS_NULL = FALSE
    NULL_IF = ()
    ERROR_ON_COLUMN_COUNT_MISMATCH = TRUE;

CREATE STAGE IF NOT EXISTS NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES_STAGE
    FILE_FORMAT = NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES_CSV;

USE ROLE SECURITYADMIN;
GRANT SELECT ON TABLE NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
    TO ROLE NORTHBRIDGE_DBT_DEV;

USE ROLE SYSADMIN;
DESCRIBE TABLE NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES;
