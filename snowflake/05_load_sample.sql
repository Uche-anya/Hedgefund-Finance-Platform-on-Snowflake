-- Run after 04_sample_stage.sql and the manual upload of both CSVs.
-- Live execution UNVERIFIED. This loads only the fixed learning delivery.
USE ROLE ACCOUNTADMIN;
GRANT USAGE ON WAREHOUSE COMPUTE_WH TO ROLE SYSADMIN;
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

COPY INTO NORTHBRIDGE_DEV.RAW.EXECUTIONS (
    business_date, execution_id, instrument, side, quantity,
    source_system, delivery_id, source_file, source_row_number
)
FROM (
    SELECT
        t.$1, t.$2, t.$3, t.$4, t.$5,
        'simulated_oms',
        '18ae80085f1043789b5d604ee44dc216',
        METADATA$FILENAME,
        METADATA$FILE_ROW_NUMBER
    FROM @NORTHBRIDGE_DEV.RAW.OMS_SAMPLE_20250106 t
)
FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.OMS_CSV')
PATTERN = '.*executions[.]csv([.]gz)?'
ON_ERROR = ABORT_STATEMENT
FORCE = FALSE;

COPY INTO NORTHBRIDGE_DEV.RAW.ALLOCATIONS (
    business_date, allocation_id, execution_id, portfolio, quantity,
    source_system, delivery_id, source_file, source_row_number
)
FROM (
    SELECT
        t.$1, t.$2, t.$3, t.$4, t.$5,
        'simulated_oms',
        '18ae80085f1043789b5d604ee44dc216',
        METADATA$FILENAME,
        METADATA$FILE_ROW_NUMBER
    FROM @NORTHBRIDGE_DEV.RAW.OMS_SAMPLE_20250106 t
)
FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.OMS_CSV')
PATTERN = '.*allocations[.]csv([.]gz)?'
ON_ERROR = ABORT_STATEMENT
FORCE = FALSE;

-- Expect two rows per table for this delivery. These are observations, not dbt tests.
SELECT 'EXECUTIONS' AS source_table, COUNT(*) AS row_count
FROM NORTHBRIDGE_DEV.RAW.EXECUTIONS
WHERE source_system = 'simulated_oms'
  AND delivery_id = '18ae80085f1043789b5d604ee44dc216'
UNION ALL
SELECT 'ALLOCATIONS', COUNT(*)
FROM NORTHBRIDGE_DEV.RAW.ALLOCATIONS
WHERE source_system = 'simulated_oms'
  AND delivery_id = '18ae80085f1043789b5d604ee44dc216';

SELECT * FROM NORTHBRIDGE_DEV.RAW.EXECUTIONS
WHERE source_system = 'simulated_oms'
  AND delivery_id = '18ae80085f1043789b5d604ee44dc216'
ORDER BY execution_id;

SELECT * FROM NORTHBRIDGE_DEV.RAW.ALLOCATIONS
WHERE source_system = 'simulated_oms'
  AND delivery_id = '18ae80085f1043789b5d604ee44dc216'
ORDER BY allocation_id;
