USE ROLE SYSADMIN;

SELECT name, state, scheduled_time, completed_time, error_code, error_message
FROM TABLE(NORTHBRIDGE_DEV.INFORMATION_SCHEMA.TASK_HISTORY(
    SCHEDULED_TIME_RANGE_START => DATEADD('hour', -1, CURRENT_TIMESTAMP()),
    TASK_NAME => 'DAILY_CLOSE',
    RESULT_LIMIT => 10
))
ORDER BY scheduled_time DESC;

SELECT task_name, event_type, business_date, recorded_at
FROM NORTHBRIDGE_DEV.OPERATIONS.TASK_RUN_AUDIT
ORDER BY recorded_at DESC
LIMIT 5;
