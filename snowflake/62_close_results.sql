-- Development close history. Run after 60_close_input_tables.sql.
USE ROLE SYSADMIN;

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS (
    attempt_id VARCHAR NOT NULL,
    request_id VARCHAR NOT NULL,
    started_at TIMESTAMP_TZ NOT NULL,
    finished_at TIMESTAMP_TZ,
    attempt_status VARCHAR NOT NULL,
    error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS (
    request_id VARCHAR NOT NULL,
    supersedes_request_id VARCHAR,
    attempt_id VARCHAR NOT NULL,
    captured_at TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP() NOT NULL,
    nav_rows NUMBER(38, 0) NOT NULL,
    nav_total NUMBER(38, 12),
    nav_hash NUMBER(38, 0),
    position_rows NUMBER(38, 0) NOT NULL,
    position_total NUMBER(38, 12),
    position_hash NUMBER(38, 0),
    result_status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS (
    request_id VARCHAR NOT NULL,
    record_type VARCHAR NOT NULL,
    business_date DATE NOT NULL,
    account_id VARCHAR NOT NULL,
    security_id VARCHAR,
    row_data VARIANT NOT NULL
);

-- These are standard tables. The capture script checks for duplicate request
-- results and inserts a result and its rows in one transaction.
