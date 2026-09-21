-- Run after 10_execution_terms.sql and uploading execution_terms.csv
-- to the existing OMS_SAMPLE_20250106 stage. Fixed sample delivery only.
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

LIST @NORTHBRIDGE_DEV.RAW.OMS_SAMPLE_20250106;

COPY INTO NORTHBRIDGE_DEV.RAW.EXECUTION_TERMS (
    business_date, execution_id, currency, execution_price, settlement_due,
    source_system, delivery_id, source_file, source_row_number
)
FROM (
    SELECT t.$1, t.$2, t.$3, t.$4, t.$5,
        'simulated_oms',
        '18ae80085f1043789b5d604ee44dc216',
        METADATA$FILENAME,
        METADATA$FILE_ROW_NUMBER
    FROM @NORTHBRIDGE_DEV.RAW.OMS_SAMPLE_20250106 t
)
FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.OMS_CSV')
PATTERN = '.*execution_terms[.]csv([.]gz)?'
ON_ERROR = ABORT_STATEMENT
FORCE = FALSE;

-- Expect two records in this delivery.
SELECT COUNT(*) AS loaded_rows
FROM NORTHBRIDGE_DEV.RAW.EXECUTION_TERMS
WHERE source_system = 'simulated_oms'
  AND delivery_id = '18ae80085f1043789b5d604ee44dc216';

SELECT business_date, execution_id, currency, execution_price, settlement_due
FROM NORTHBRIDGE_DEV.RAW.EXECUTION_TERMS
WHERE source_system = 'simulated_oms'
  AND delivery_id = '18ae80085f1043789b5d604ee44dc216'
ORDER BY execution_id;
