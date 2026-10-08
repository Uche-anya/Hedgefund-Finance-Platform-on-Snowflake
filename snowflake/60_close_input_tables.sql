-- Run once in development after 38_delivery_readiness.sql.
-- Applied in NORTHBRIDGE_DEV on 7 October 2026.
USE ROLE SYSADMIN;

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS (
    request_id VARCHAR NOT NULL,
    scenario_id VARCHAR NOT NULL,
    business_date DATE NOT NULL,
    cutoff_at TIMESTAMP_TZ NOT NULL,
    model_sha256 VARCHAR NOT NULL,
    seed_sha256 VARCHAR NOT NULL,
    expected_input_count NUMBER(38, 0) NOT NULL,
    request_status VARCHAR NOT NULL,
    raw_verified_at TIMESTAMP_TZ NOT NULL,
    created_at TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP() NOT NULL,
    created_by VARCHAR DEFAULT CURRENT_USER() NOT NULL
);

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUTS (
    request_id VARCHAR NOT NULL,
    source_name VARCHAR NOT NULL,
    delivery_id VARCHAR NOT NULL,
    file_sha256 VARCHAR NOT NULL,
    receipt_sha256 VARCHAR,
    expected_rows NUMBER(38, 0) NOT NULL,
    verified_raw_rows NUMBER(38, 0) NOT NULL,
    evidence_status VARCHAR NOT NULL,
    registered_at TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP() NOT NULL
);

-- Snowflake standard-table uniqueness is not enforced. The registration
-- process must reject duplicate request IDs and source/delivery pairs.
USE ROLE SECURITYADMIN;
GRANT SELECT ON TABLE NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS
    TO ROLE NORTHBRIDGE_DBT_DEV;
GRANT SELECT ON TABLE NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUTS
    TO ROLE NORTHBRIDGE_DBT_DEV;
