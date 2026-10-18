-- DEV is for manual validation. The unattended close will move to PROD.
-- Keep the task definitions so we can still inspect or manually exercise them.
USE ROLE NORTHBRIDGE_DBT_DEV;

ALTER TASK IF EXISTS NORTHBRIDGE_DEV.DBT_DEV.DAILY_CLOSE_READY SUSPEND;
ALTER TASK IF EXISTS NORTHBRIDGE_DEV.DBT_DEV.DAILY_CLOSE_DEADLINE SUSPEND;

SHOW TASKS IN SCHEMA NORTHBRIDGE_DEV.DBT_DEV
    ->> SELECT "name", "state" FROM $1 ORDER BY 1;
