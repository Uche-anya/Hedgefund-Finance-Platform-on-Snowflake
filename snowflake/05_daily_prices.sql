-- Market data is independent of the simulated fund scenario.
-- Keep the provider row intact; parsing and security mapping come later.
USE ROLE SYSADMIN;

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.RAW.DAILY_PRICE_EVENTS (
    payload VARIANT,
    source_file VARCHAR,
    source_row_number NUMBER,
    loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
);

USE ROLE SECURITYADMIN;
GRANT SELECT, INSERT ON TABLE NORTHBRIDGE_DEV.RAW.DAILY_PRICE_EVENTS
    TO ROLE NORTHBRIDGE_INGEST_DEV;
