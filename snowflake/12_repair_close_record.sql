-- Replace only the failed record procedure; leave the task graph as deployed.
USE ROLE SYSADMIN;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_DEV.DBT_DEV.RECORD_DAILY_CLOSE(
    CLOSE_DATE DATE, SCENARIO VARCHAR, OPENING_DATE DATE)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    nav_count NUMBER;
    account_count NUMBER;
    priced_count NUMBER;
    previous_count NUMBER;
    bad_nav EXCEPTION(-20001, 'Expected one NAV per account');
BEGIN
    SELECT COUNT(*), COUNT(DISTINCT account_id), COUNT(nav_usd)
        INTO :nav_count, :account_count, :priced_count
    FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_NAV_DAILY
    WHERE valuation_date = :CLOSE_DATE AND scenario_id = :SCENARIO;
    IF (nav_count != 2 OR account_count != 2 OR priced_count != 2) THEN
        RAISE bad_nav;
    END IF;
    SELECT COUNT(*) INTO :previous_count
    FROM NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS
    WHERE business_date = :CLOSE_DATE AND scenario_id = :SCENARIO
      AND status = 'VALIDATED';
    IF (previous_count > 0) THEN
        RETURN 'ALREADY_VALIDATED';
    END IF;
    INSERT INTO NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS
        (run_id, business_date, scenario_id, opening_date, status, detail, finished_at)
    SELECT UUID_STRING(), :CLOSE_DATE, :SCENARIO, :OPENING_DATE,
           'VALIDATED', 'Snowflake dbt project build passed', CURRENT_TIMESTAMP();
    RETURN 'VALIDATED';
END;
$$;
