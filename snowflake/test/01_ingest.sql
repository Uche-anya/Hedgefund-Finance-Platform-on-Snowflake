
USE ROLE SYSADMIN;

CREATE FILE FORMAT IF NOT EXISTS NORTHBRIDGE_TEST.RAW.DAILY_JSON
    TYPE = JSON COMPRESSION = NONE;
CREATE STAGE IF NOT EXISTS NORTHBRIDGE_TEST.RAW.DAILY_LANDING
    FILE_FORMAT = NORTHBRIDGE_TEST.RAW.DAILY_JSON;

CREATE PIPE IF NOT EXISTS NORTHBRIDGE_TEST.RAW.DAILY_OMS_PIPE
    AUTO_INGEST = FALSE
    AS COPY INTO NORTHBRIDGE_TEST.RAW.DAILY_OMS_EVENTS
        (payload, source_file, source_row_number)
    FROM (
        SELECT t.$1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
        FROM @NORTHBRIDGE_TEST.RAW.DAILY_LANDING/oms/ t
    )
    FILE_FORMAT = (FORMAT_NAME = NORTHBRIDGE_TEST.RAW.DAILY_JSON)
    PATTERN = '.*[.]jsonl'
    ON_ERROR = SKIP_FILE;

CREATE PIPE IF NOT EXISTS NORTHBRIDGE_TEST.RAW.DAILY_SETTLEMENT_PIPE
    AUTO_INGEST = FALSE
    AS COPY INTO NORTHBRIDGE_TEST.RAW.DAILY_SETTLEMENT_EVENTS
        (payload, source_file, source_row_number)
    FROM (
        SELECT t.$1, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
        FROM @NORTHBRIDGE_TEST.RAW.DAILY_LANDING/settlements/ t
    )
    FILE_FORMAT = (FORMAT_NAME = NORTHBRIDGE_TEST.RAW.DAILY_JSON)
    PATTERN = '.*[.]jsonl'
    ON_ERROR = SKIP_FILE;

-- Four TEST candidates cover the rehearsal day; later DEV mappings begin Oct 8.
MERGE INTO NORTHBRIDGE_TEST.RAW.SECURITY_MAPPINGS m
USING (
    SELECT column1 AS instrument_id, column2 AS provider_ticker
    FROM VALUES ('AAPL.US', 'AAPL'), ('AMZN.US', 'AMZN'),
                ('MSFT.US', 'MSFT'), ('KO.US', 'KO')
) c
ON m.instrument_id = c.instrument_id AND m.valid_from = '2026-10-06'::date
WHEN NOT MATCHED THEN INSERT
    (instrument_id, provider_ticker, valid_from, valid_to, status, note)
    VALUES (c.instrument_id, c.provider_ticker,
            '2026-10-06'::date, '2026-10-07'::date,
            'PENDING', 'TEST first-day rehearsal');
