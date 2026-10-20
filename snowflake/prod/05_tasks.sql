-- Keep the root suspended while changing this graph. Start it only after the next-day rehearsal.
USE ROLE NORTHBRIDGE_TASK_PROD;

ALTER TASK IF EXISTS NORTHBRIDGE_PROD.DBT_PROD.DAILY_CLOSE_READY SUSPEND;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_PROD.DBT_PROD.CHECK_DIVIDEND_INPUT(
    CLOSE_DATE DATE)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    delivery_count NUMBER;
    ready_count NUMBER;
BEGIN
    SELECT COUNT(*), COUNT_IF(
        d.status = 'LOADED' AND d.expected_rows > 0
        AND d.expected_rows = COALESCE(r.loaded_rows, 0))
      INTO :delivery_count, :ready_count
    FROM (
        SELECT stage_path, expected_rows, status
        FROM NORTHBRIDGE_PROD.RAW.DAILY_DELIVERIES
        WHERE source_name = 'dividends' AND scenario_id = 'massive'
          AND business_date = :CLOSE_DATE
        QUALIFY ROW_NUMBER() OVER (
            ORDER BY registered_at DESC, delivery_id DESC) = 1
    ) d
    LEFT JOIN (
        SELECT source_file, COUNT(*) AS loaded_rows
        FROM NORTHBRIDGE_PROD.RAW.DAILY_DIVIDEND_EVENTS
        GROUP BY source_file
    ) r ON ENDSWITH(r.source_file, d.stage_path);

    IF (delivery_count != 1 OR COALESCE(ready_count, 0) != 1) THEN
        RETURN 'WAITING_DIVIDENDS';
    END IF;
    RETURN 'READY';
END;
$$;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_PROD.DBT_PROD.CHECK_BANK_INPUT(
    CLOSE_DATE DATE, SCENARIO VARCHAR)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    delivery_count NUMBER;
    ready_count NUMBER;
    bank_rows NUMBER;
    account_count NUMBER;
    bad_rows NUMBER;
BEGIN
    SELECT COUNT(*), COUNT_IF(status = 'LOADED' AND expected_rows = 2)
      INTO :delivery_count, :ready_count
    FROM NORTHBRIDGE_PROD.RAW.DAILY_DELIVERIES
    WHERE source_name = 'bank' AND business_date = :CLOSE_DATE
      AND scenario_id = :SCENARIO;
    IF (delivery_count != 1 OR COALESCE(ready_count, 0) != 1) THEN
        RETURN 'WAITING_BANK';
    END IF;

    SELECT COUNT(*), COUNT(DISTINCT r.payload:account_id::varchar),
        COUNT_IF(COALESCE(r.payload:scenario_id::varchar, '') != :SCENARIO
            OR TRY_TO_DATE(r.payload:statement_date::varchar) IS NULL
            OR TRY_TO_DATE(r.payload:statement_date::varchar) != :CLOSE_DATE
            OR COALESCE(r.payload:currency::varchar, '') != 'USD'
            OR COALESCE(r.payload:source_system::varchar, '') != 'simulated_bank'
            OR TRY_TO_DECIMAL(r.payload:closing_balance::varchar, 38, 2) IS NULL)
      INTO :bank_rows, :account_count, :bad_rows
    FROM NORTHBRIDGE_PROD.RAW.DAILY_BANK_STATEMENTS r
    JOIN NORTHBRIDGE_PROD.RAW.DAILY_DELIVERIES d
        ON d.source_name = 'bank' AND d.business_date = :CLOSE_DATE
        AND d.scenario_id = :SCENARIO AND d.status = 'LOADED'
        AND ENDSWITH(r.source_file, d.stage_path);
    IF (bank_rows != 2 OR account_count != 2 OR COALESCE(bad_rows, 0) != 0) THEN
        RETURN 'WAITING_BANK';
    END IF;
    RETURN 'READY';
END;
$$;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_PROD.DBT_PROD.CHECK_DAILY_INPUTS(
    CLOSE_DATE DATE, SCENARIO VARCHAR, OPENING_DATE DATE)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE
    source_count NUMBER;
    ready_count NUMBER;
    missing_prices NUMBER;
    completed_count NUMBER;
    state VARCHAR;
    dividend_state VARCHAR;
    bank_state VARCHAR;
BEGIN
    SELECT COUNT(*) INTO :completed_count
    FROM NORTHBRIDGE_PROD.RAW.DAILY_CLOSE_RUNS
    WHERE business_date = :CLOSE_DATE AND scenario_id = :SCENARIO
      AND status = 'VALIDATED';
    IF (completed_count > 0) THEN
        RETURN 'ALREADY_VALIDATED';
    END IF;

    SELECT COUNT(*), COUNT_IF(
        (expected_rows = 0 AND status = 'EMPTY' AND loaded_rows = 0)
        OR (expected_rows > 0 AND status IN ('SUBMITTED', 'LOADED')
            AND expected_rows = loaded_rows))
      INTO :source_count, :ready_count
    FROM (
        SELECT d.source_name, d.expected_rows, d.status,
            COALESCE(SUM(l.row_count), 0) AS loaded_rows
        FROM NORTHBRIDGE_PROD.RAW.DAILY_DELIVERIES d
        LEFT JOIN (
            SELECT 'oms' AS source_name, source_file, COUNT(*) AS row_count
            FROM NORTHBRIDGE_PROD.RAW.DAILY_OMS_EVENTS GROUP BY 2
            UNION ALL
            SELECT 'settlements', source_file, COUNT(*)
            FROM NORTHBRIDGE_PROD.RAW.DAILY_SETTLEMENT_EVENTS GROUP BY 2
            UNION ALL
            SELECT 'prices', source_file, COUNT(*)
            FROM NORTHBRIDGE_PROD.RAW.DAILY_PRICE_EVENTS GROUP BY 2
            UNION ALL
            SELECT 'opening_bank', source_file, COUNT(*)
            FROM NORTHBRIDGE_PROD.RAW.DAILY_OPENING_EVENTS GROUP BY 2
            UNION ALL
            SELECT 'opening_admin', source_file, COUNT(*)
            FROM NORTHBRIDGE_PROD.RAW.DAILY_OPENING_EVENTS GROUP BY 2
        ) l ON l.source_name = d.source_name
            AND ENDSWITH(l.source_file, d.stage_path)
        WHERE (d.business_date = :CLOSE_DATE AND d.scenario_id = :SCENARIO
               AND d.source_name IN ('oms', 'settlements'))
           OR (d.business_date = :CLOSE_DATE AND d.scenario_id = 'massive'
               AND d.source_name = 'prices')
           OR (d.business_date = :OPENING_DATE AND d.scenario_id = :SCENARIO
               AND d.source_name IN ('opening_bank', 'opening_admin'))
        GROUP BY d.source_name, d.expected_rows, d.status, d.delivery_id
    );

    IF (source_count != 5 OR ready_count != 5) THEN
        state := 'WAITING_INPUTS';
        RETURN state;
    END IF;

    CALL NORTHBRIDGE_PROD.DBT_PROD.CHECK_DIVIDEND_INPUT(:CLOSE_DATE)
        INTO :dividend_state;
    IF (dividend_state != 'READY') THEN
        RETURN dividend_state;
    END IF;

    CALL NORTHBRIDGE_PROD.DBT_PROD.CHECK_BANK_INPUT(:CLOSE_DATE, :SCENARIO)
        INTO :bank_state;
    IF (bank_state != 'READY') THEN
        RETURN bank_state;
    END IF;

    SELECT COUNT(*) INTO :missing_prices
    FROM (
        SELECT r.payload:market_ticker::varchar AS ticker,
            SUM(CASE r.payload:side::varchar
                WHEN 'BUY' THEN TRY_TO_DECIMAL(r.payload:quantity::varchar, 38, 9)
                WHEN 'SELL' THEN -TRY_TO_DECIMAL(r.payload:quantity::varchar, 38, 9)
            END) AS shares
        FROM NORTHBRIDGE_PROD.RAW.DAILY_OMS_EVENTS r
        JOIN NORTHBRIDGE_PROD.RAW.DAILY_DELIVERIES d
            ON d.source_name = 'oms' AND d.scenario_id = :SCENARIO
            AND d.business_date <= :CLOSE_DATE AND d.status = 'SUBMITTED'
            AND ENDSWITH(r.source_file, d.stage_path)
        GROUP BY 1
        HAVING shares <> 0
    ) held
    LEFT JOIN (
        SELECT r.payload:universe_ticker::varchar AS ticker,
            COUNT(*) AS price_rows
        FROM NORTHBRIDGE_PROD.RAW.DAILY_PRICE_EVENTS r
        JOIN NORTHBRIDGE_PROD.RAW.DAILY_DELIVERIES d
            ON d.source_name = 'prices' AND d.scenario_id = 'massive'
            AND d.business_date = :CLOSE_DATE AND d.status = 'LOADED'
            AND ENDSWITH(r.source_file, d.stage_path)
        WHERE TRY_TO_DECIMAL(r.payload:close_price::varchar, 38, 9) > 0
          AND r.payload:currency::varchar = 'USD'
          AND r.payload:price_basis::varchar = 'unadjusted'
        GROUP BY 1
    ) priced ON priced.ticker = held.ticker
    WHERE priced.price_rows IS NULL OR priced.price_rows != 1;

    IF (missing_prices > 0) THEN
        state := 'WAITING_PRICES';
    ELSE
        state := 'READY:' || TO_VARCHAR(CLOSE_DATE, 'YYYY-MM-DD');
    END IF;
    RETURN state;
END;
$$;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_PROD.DBT_PROD.SET_DAILY_TASK_STATE(
    CLOSE_DATE DATE, SCENARIO VARCHAR, OPENING_DATE DATE)
RETURNS VARCHAR
LANGUAGE SQL
EXECUTE AS CALLER
AS
$$
DECLARE state VARCHAR;
BEGIN
    CALL NORTHBRIDGE_PROD.DBT_PROD.CHECK_DAILY_INPUTS(
        :CLOSE_DATE, :SCENARIO, :OPENING_DATE) INTO :state;
    CALL SYSTEM$SET_RETURN_VALUE(:state);
    RETURN state;
END;
$$;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_PROD.DBT_PROD.RECORD_DAILY_CLOSE(
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
    cash_count NUMBER;
    cash_matches NUMBER;
    bad_nav EXCEPTION(-20001, 'Expected one NAV per account');
    bad_cash EXCEPTION(-20002, 'Bank cash does not reconcile');
BEGIN
    SELECT COUNT(*), COUNT(DISTINCT account_id), COUNT(nav_usd)
        INTO :nav_count, :account_count, :priced_count
    FROM NORTHBRIDGE_PROD.DBT_PROD.FCT_NAV_DAILY
    WHERE valuation_date = :CLOSE_DATE AND scenario_id = :SCENARIO;
    IF (nav_count != 2 OR account_count != 2 OR priced_count != 2) THEN
        RAISE bad_nav;
    END IF;
    SELECT COUNT(*) INTO :previous_count
    FROM NORTHBRIDGE_PROD.RAW.DAILY_CLOSE_RUNS
    WHERE business_date = :CLOSE_DATE AND scenario_id = :SCENARIO
      AND status = 'VALIDATED';
    IF (previous_count > 0) THEN
        RETURN 'ALREADY_VALIDATED';
    END IF;
    SELECT COUNT(*), COUNT_IF(reconciliation_status = 'MATCH')
        INTO :cash_count, :cash_matches
    FROM NORTHBRIDGE_PROD.DBT_PROD.FCT_CASH_RECONCILIATION
    WHERE statement_date = :CLOSE_DATE AND scenario_id = :SCENARIO;
    IF (cash_count != 2 OR COALESCE(cash_matches, 0) != 2) THEN
        RAISE bad_cash;
    END IF;
    INSERT INTO NORTHBRIDGE_PROD.RAW.DAILY_CLOSE_RUNS
        (run_id, business_date, scenario_id, opening_date, status, detail, finished_at)
    SELECT UUID_STRING(), :CLOSE_DATE, :SCENARIO, :OPENING_DATE,
           'VALIDATED', 'Snowflake dbt project build passed', CURRENT_TIMESTAMP();
    RETURN 'VALIDATED';
END;
$$;

CREATE OR ALTER TASK NORTHBRIDGE_PROD.DBT_PROD.DAILY_CLOSE_READY
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = 'USING CRON 0 2-7 * * TUE-SAT America/New_York'
    CONFIG = $${"business_date": null}$$
AS
    CALL NORTHBRIDGE_PROD.DBT_PROD.SET_DAILY_TASK_STATE(
        COALESCE(
            TRY_TO_DATE(SYSTEM$GET_TASK_GRAPH_CONFIG('business_date')::varchar),
            DATEADD(day, -1, CONVERT_TIMEZONE('America/New_York', CURRENT_TIMESTAMP())::date)
        ),
        'sim-prod-20261016', '2026-10-15'::date);

CREATE OR ALTER TASK NORTHBRIDGE_PROD.DBT_PROD.DAILY_CLOSE_BUILD
    WAREHOUSE = COMPUTE_WH
    AFTER NORTHBRIDGE_PROD.DBT_PROD.DAILY_CLOSE_READY
    WHEN SYSTEM$GET_PREDECESSOR_RETURN_VALUE('DAILY_CLOSE_READY') != 'WAITING_INPUTS'
     AND SYSTEM$GET_PREDECESSOR_RETURN_VALUE('DAILY_CLOSE_READY') != 'WAITING_DIVIDENDS'
     AND SYSTEM$GET_PREDECESSOR_RETURN_VALUE('DAILY_CLOSE_READY') != 'WAITING_BANK'
     AND SYSTEM$GET_PREDECESSOR_RETURN_VALUE('DAILY_CLOSE_READY') != 'WAITING_PRICES'
     AND SYSTEM$GET_PREDECESSOR_RETURN_VALUE('DAILY_CLOSE_READY') != 'ALREADY_VALIDATED'
AS
    EXECUTE DBT PROJECT NORTHBRIDGE_PROD.DBT_PROD.NORTHBRIDGE_DAILY
        ARGS = 'build --target prod'
        DBT_VERSION = '1.12.3'
        ENV_VARS = (
            'DBT_BUSINESS_DATE' = '{{ select substr(SYSTEM$GET_PREDECESSOR_RETURN_VALUE(\'DAILY_CLOSE_READY\'), 7) }}',
            'DBT_OPENING_DATE' = '2026-10-15',
            'DBT_SCENARIO_ID' = 'sim-prod-20261016'
        );

CREATE OR ALTER TASK NORTHBRIDGE_PROD.DBT_PROD.DAILY_CLOSE_RECORD
    WAREHOUSE = COMPUTE_WH
    AFTER NORTHBRIDGE_PROD.DBT_PROD.DAILY_CLOSE_BUILD
AS
    CALL NORTHBRIDGE_PROD.DBT_PROD.RECORD_DAILY_CLOSE(
        TO_DATE(SUBSTR(SYSTEM$GET_PREDECESSOR_RETURN_VALUE('DAILY_CLOSE_READY'), 7)),
        'sim-prod-20261016', '2026-10-15'::date);

-- The task role keeps ownership. The person who installed it does not need
-- the role after deployment. If deployment stops early, run these three
-- statements separately to remove the personal grant.
USE ROLE SECURITYADMIN;
SET task_deployer = CURRENT_USER();
REVOKE ROLE NORTHBRIDGE_TASK_PROD FROM USER IDENTIFIER($task_deployer);
