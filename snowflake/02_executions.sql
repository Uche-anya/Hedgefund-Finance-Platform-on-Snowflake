-- Incoming CSV fields stay as text. dbt will validate and convert them.
-- Live execution: UNVERIFIED until run in the development account.
USE ROLE SYSADMIN;

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.RAW.EXECUTIONS (
    business_date VARCHAR,
    execution_id VARCHAR,
    instrument VARCHAR,
    side VARCHAR,
    quantity VARCHAR,
    source_system VARCHAR NOT NULL,
    delivery_id VARCHAR NOT NULL,
    source_file VARCHAR NOT NULL,
    source_row_number NUMBER(38, 0) NOT NULL,
    loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP() NOT NULL
);

DESCRIBE TABLE NORTHBRIDGE_DEV.RAW.EXECUTIONS;
