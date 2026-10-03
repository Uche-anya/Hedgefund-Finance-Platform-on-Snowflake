-- Read-only evidence for the most recently registered controlled run.
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

SET checked_run = (
    SELECT run_id
    FROM NORTHBRIDGE_DEV.OPERATIONS.RUNS
    ORDER BY created_at DESC
    LIMIT 1
);

SELECT
    run_id,
    run_mode,
    business_date,
    latest_attempt,
    current_status,
    status_changed_at
FROM NORTHBRIDGE_DEV.OPERATIONS.CURRENT_RUN_STATUS
WHERE run_id = $checked_run;

SELECT source_name, delivery_id, expected_rows
FROM NORTHBRIDGE_DEV.OPERATIONS.RUN_INPUTS
WHERE run_id = $checked_run
ORDER BY source_name;

SELECT attempt_number, step_name, event_type, occurred_at, details
FROM NORTHBRIDGE_DEV.OPERATIONS.RUN_EVENTS
WHERE run_id = $checked_run
ORDER BY occurred_at, event_id;
