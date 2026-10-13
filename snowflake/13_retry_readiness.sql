-- Check again if a submitted delivery is still loading at the first check.
-- The root remains suspended until the full daily run has been tested.
USE ROLE NORTHBRIDGE_DBT_DEV;

ALTER TASK NORTHBRIDGE_DEV.DBT_DEV.DAILY_CLOSE_READY
    SET SCHEDULE = 'USING CRON 0 2-5 * * TUE-SAT America/New_York';
