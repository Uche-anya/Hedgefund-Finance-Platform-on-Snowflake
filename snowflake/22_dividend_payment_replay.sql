USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

PUT 'file://C:/Users/UCHE/Desktop/Hedgefund-Finance-Pipeline-on-Snowflake/data/replays/sim-dividend-a48996d29c0473a090db3b9f/records.jsonl'
    @NORTHBRIDGE_DEV.RAW.REPLAY_STAGE/sim-dividend-a48996d29c0473a090db3b9f/
    AUTO_COMPRESS = TRUE OVERWRITE = FALSE;
COPY INTO NORTHBRIDGE_DEV.RAW.REPLAY_INPUTS
    (payload, delivery_id, source_file, source_row_number)
FROM (
    SELECT t.$1, 'sim-dividend-a48996d29c0473a090db3b9f', METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
    FROM @NORTHBRIDGE_DEV.RAW.REPLAY_STAGE/sim-dividend-a48996d29c0473a090db3b9f/ t
)
FILES = ('records.jsonl.gz')
FILE_FORMAT = (FORMAT_NAME = 'NORTHBRIDGE_DEV.RAW.REPLAY_JSON')
ON_ERROR = ABORT_STATEMENT FORCE = FALSE;

SELECT payload:record_type::varchar AS record_type, COUNT(*) AS records
FROM NORTHBRIDGE_DEV.RAW.REPLAY_INPUTS
WHERE delivery_id = 'sim-dividend-a48996d29c0473a090db3b9f'
GROUP BY record_type;
