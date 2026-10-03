-- Run with Snowflake CLI: PUT reads files from this computer.
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

PUT 'file://C:/Users/UCHE/Desktop/Hedgefund-Finance-Pipeline-on-Snowflake/data/simulator_historical/sim-historical-f9b72e1aa20041068cea4d5ac0b2eaf8/*.jsonl'
    @NORTHBRIDGE_DEV.RAW.OMS_EVENTS_STAGE/sim-historical-f9b72e1aa20041068cea4d5ac0b2eaf8/
    AUTO_COMPRESS = TRUE OVERWRITE = FALSE;

-- This lesson delivers one complete scenario in one batch.
COPY INTO NORTHBRIDGE_DEV.RAW.OMS_EVENTS (
    payload, source_system, scenario_id, delivery_id,
    source_file, source_row_number
)
FROM (
    SELECT
        t.$1,
        t.$1:source_system::VARCHAR,
        t.$1:scenario_id::VARCHAR,
        'sim-historical-f9b72e1aa20041068cea4d5ac0b2eaf8',
        METADATA$FILENAME,
        METADATA$FILE_ROW_NUMBER
    FROM @NORTHBRIDGE_DEV.RAW.OMS_EVENTS_STAGE/sim-historical-f9b72e1aa20041068cea4d5ac0b2eaf8/ t
)
FILES = (
    'sim-event-65bc6285f33a4134b17b24203367e7c6.jsonl.gz',
    'sim-event-8390e97e7bd94d8191c6e5703ba059b5.jsonl.gz',
    'sim-event-44c36b592f7040ec9eaac440288177c2.jsonl.gz',
    'sim-event-bf8211379ba04580a5b707ada1183f9d.jsonl.gz',
    'sim-event-92010fd009f14e0d95cb85a8b86dfb10.jsonl.gz'
)
FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.OMS_JSON')
ON_ERROR = ABORT_STATEMENT
FORCE = FALSE;

-- All four counts should be five.
SELECT
    COUNT(*) AS rows_loaded,
    COUNT(DISTINCT payload:event_id::VARCHAR) AS events,
    COUNT(DISTINCT payload:execution_id::VARCHAR) AS executions,
    COUNT_IF(payload:is_simulated::BOOLEAN) AS simulated
FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
WHERE delivery_id = 'sim-historical-f9b72e1aa20041068cea4d5ac0b2eaf8';

SELECT
    payload:business_date::VARCHAR AS business_date,
    payload:market_ticker::VARCHAR AS ticker,
    payload:side::VARCHAR AS side,
    payload:quantity::VARCHAR AS quantity,
    payload:execution_price::VARCHAR AS execution_price
FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
WHERE delivery_id = 'sim-historical-f9b72e1aa20041068cea4d5ac0b2eaf8'
ORDER BY payload:executed_at::VARCHAR;
