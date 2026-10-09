-- One row per attempt. A validated run is a checked calculation, not publication.
USE ROLE SYSADMIN;
CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS (
    run_id VARCHAR,
    business_date DATE,
    scenario_id VARCHAR,
    opening_date DATE,
    status VARCHAR,
    detail VARCHAR,
    started_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(),
    finished_at TIMESTAMP_LTZ
);

USE ROLE SECURITYADMIN;
GRANT SELECT, INSERT, UPDATE ON TABLE NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS
    TO ROLE NORTHBRIDGE_INGEST_DEV;
