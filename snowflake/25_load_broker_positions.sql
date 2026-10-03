USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

PUT 'file:///C:/Users/UCHE/Desktop/Hedgefund-Finance-Pipeline-on-Snowflake/data/broker_statements/sim-broker-42a53a52c3913f138bf0ba35/positions.jsonl'
    @NORTHBRIDGE_DEV.RAW.BROKER_POSITIONS_STAGE/sim-broker-42a53a52c3913f138bf0ba35/
    AUTO_COMPRESS = TRUE OVERWRITE = FALSE;

COPY INTO NORTHBRIDGE_DEV.RAW.BROKER_POSITIONS
    (payload, delivery_id, source_file, source_row_number)
FROM (
    SELECT
        t.$1,
        'sim-broker-42a53a52c3913f138bf0ba35',
        METADATA$FILENAME,
        METADATA$FILE_ROW_NUMBER
    FROM @NORTHBRIDGE_DEV.RAW.BROKER_POSITIONS_STAGE/sim-broker-42a53a52c3913f138bf0ba35/ t
)
FILES = ('positions.jsonl.gz')
FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.BROKER_POSITIONS_JSON')
ON_ERROR = ABORT_STATEMENT
FORCE = FALSE;

SELECT
    COUNT(*) AS loaded_rows,
    COUNT(DISTINCT payload:account_id::varchar) AS accounts,
    MIN(payload:statement_date::date) AS statement_date
FROM NORTHBRIDGE_DEV.RAW.BROKER_POSITIONS
WHERE delivery_id = 'sim-broker-42a53a52c3913f138bf0ba35';
