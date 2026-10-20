-- Keep checking after the 5:30 a.m. deadline so a late delivery can recover.
-- Changes to this running task graph require suspending the root first.
USE ROLE NORTHBRIDGE_DBT_DEV;

ALTER TASK NORTHBRIDGE_DEV.DBT_DEV.DAILY_CLOSE_READY SUSPEND;
ALTER TASK NORTHBRIDGE_DEV.DBT_DEV.DAILY_CLOSE_READY
    SET SCHEDULE = 'USING CRON 0 2-7 * * TUE-SAT America/New_York';
-- Leave DEV suspended after changing the schedule. PROD owns unattended runs.
