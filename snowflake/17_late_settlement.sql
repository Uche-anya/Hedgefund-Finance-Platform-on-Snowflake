-- Add only the missing confirmation. Keep the original delivery intact.
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;
PUT 'file://C:/Users/UCHE/Desktop/Hedgefund-Finance-Pipeline-on-Snowflake/data/simulator_settlements/2cfd3d50543c480dbbd15dae315c2cfa/*.jsonl'
    @NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS_STAGE/2cfd3d50543c480dbbd15dae315c2cfa/
    AUTO_COMPRESS = TRUE OVERWRITE = FALSE;
COPY INTO NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS
    (payload, delivery_id, source_file, source_row_number)
FROM (
    SELECT t.$1, '2cfd3d50543c480dbbd15dae315c2cfa',
        METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
    FROM @NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS_STAGE/2cfd3d50543c480dbbd15dae315c2cfa/ t
)
FILES = ('sim-settlement-008ba4e9ede35458ab743a6e914d4762.jsonl.gz')
FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.SETTLEMENT_JSON')
ON_ERROR = ABORT_STATEMENT FORCE = FALSE;

SELECT delivery_id, COUNT(*) AS events
FROM NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS
WHERE delivery_id IN ('a98ed87facdf46f6be0fc923d59b5975', '2cfd3d50543c480dbbd15dae315c2cfa')
GROUP BY delivery_id;
