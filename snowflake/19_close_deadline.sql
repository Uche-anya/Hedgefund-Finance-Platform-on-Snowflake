-- The date list matches config/us_equity_calendar_2026.json.
-- Review and deploy the next year's calendar before 2027.
USE ROLE SYSADMIN;
CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.RAW.US_EQUITY_MARKET_CLOSED (
    closed_date DATE NOT NULL
);

MERGE INTO NORTHBRIDGE_DEV.RAW.US_EQUITY_MARKET_CLOSED t
USING (
    SELECT TO_DATE(column1) AS closed_date FROM VALUES
        ('2026-01-01'), ('2026-01-19'), ('2026-02-16'),
        ('2026-04-03'), ('2026-05-25'), ('2026-06-19'),
        ('2026-07-03'), ('2026-09-07'), ('2026-11-26'),
        ('2026-12-25')
) s
ON t.closed_date = s.closed_date
WHEN NOT MATCHED THEN INSERT (closed_date) VALUES (s.closed_date);

USE ROLE SECURITYADMIN;
GRANT SELECT ON TABLE NORTHBRIDGE_DEV.RAW.US_EQUITY_MARKET_CLOSED
    TO ROLE NORTHBRIDGE_DBT_DEV;

USE ROLE NORTHBRIDGE_DBT_DEV;
CREATE OR REPLACE PROCEDURE NORTHBRIDGE_DEV.DBT_DEV.CHECK_CLOSE_DEADLINE(
    CLOSE_DATE DATE)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    closed_count NUMBER;
    validated_count NUMBER;
    missing_close EXCEPTION(-20002, 'No single validated close by 5:30 a.m. New York time');
    unknown_calendar EXCEPTION(-20003, 'Review the US equity market calendar before this year');
BEGIN
    IF (YEAR(CLOSE_DATE) != 2026) THEN
        RAISE unknown_calendar;
    END IF;

    SELECT COUNT(*) INTO :closed_count
    FROM NORTHBRIDGE_DEV.RAW.US_EQUITY_MARKET_CLOSED
    WHERE closed_date = :CLOSE_DATE;
    IF (DAYOFWEEKISO(CLOSE_DATE) > 5 OR closed_count > 0) THEN
        RETURN 'MARKET_CLOSED';
    END IF;

    SELECT COUNT(*) INTO :validated_count
    FROM NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS
    WHERE business_date = :CLOSE_DATE
      AND scenario_id = 'sim-close-20261008'
      AND status = 'VALIDATED';
    IF (validated_count != 1) THEN
        RAISE missing_close;
    END IF;
    RETURN 'VALIDATED';
END;
$$;

-- A separate Snowflake clock checks the deadline. Later readiness runs can
-- still recover the close; they do not erase a failed deadline task run.
ALTER TASK IF EXISTS NORTHBRIDGE_DEV.DBT_DEV.DAILY_CLOSE_DEADLINE SUSPEND;
CREATE OR ALTER TASK NORTHBRIDGE_DEV.DBT_DEV.DAILY_CLOSE_DEADLINE
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = 'USING CRON 30 5 * * TUE-SAT America/New_York'
    SUSPEND_TASK_AFTER_NUM_FAILURES = 0
AS
    CALL NORTHBRIDGE_DEV.DBT_DEV.CHECK_CLOSE_DEADLINE(
        DATEADD(day, -1,
            CONVERT_TIMEZONE('America/New_York', CURRENT_TIMESTAMP())::date));
-- DEV stays suspended. Only PROD should have an unattended deadline task.
