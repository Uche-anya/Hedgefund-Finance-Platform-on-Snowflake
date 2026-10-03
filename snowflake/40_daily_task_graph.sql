-- Define the daily close graph under the same role used by the native dbt project.
-- The one-time account grant and ownership transfer are in 45_task_owner_setup.sql.
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.OPERATIONS.TASK_RUN_AUDIT (
    audit_id VARCHAR NOT NULL,
    task_name VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    business_date DATE NOT NULL,
    recorded_at TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP() NOT NULL
);

USE ROLE SECURITYADMIN;
GRANT USAGE ON DBT PROJECT NORTHBRIDGE_DEV.OPERATIONS.NORTHBRIDGE_DBT
    TO ROLE NORTHBRIDGE_DBT_DEV;
GRANT INSERT, SELECT ON TABLE NORTHBRIDGE_DEV.OPERATIONS.TASK_RUN_AUDIT
    TO ROLE NORTHBRIDGE_DBT_DEV;
GRANT CREATE TASK ON SCHEMA NORTHBRIDGE_DEV.OPERATIONS
    TO ROLE NORTHBRIDGE_DBT_DEV;

USE ROLE NORTHBRIDGE_DBT_DEV;
USE WAREHOUSE COMPUTE_WH;

CREATE OR ALTER TASK NORTHBRIDGE_DEV.OPERATIONS.DAILY_CLOSE
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = 'USING CRON 0 6 * * MON-FRI UTC'
    USER_TASK_TIMEOUT_MS = 3600000
    SUSPEND_TASK_AFTER_NUM_FAILURES = 2
    CONFIG = $$
    {
      "business_date": "2025-02-07",
      "corporate_action_load_id": "890be0cfdcf2151ebb4aab47f0d53cd9",
      "replay_delivery_id": "sim-dividend-a48996d29c0473a090db3b9f",
      "replay_scenario_id": "sim-replay-406bbef8179cdbb0a3dd6df3",
      "historical_price_delivery_id": "fb25ddd9838840488e4c8b971ff7e0ae",
      "broker_delivery_id": "sim-broker-42a53a52c3913f138bf0ba35",
      "broker_statement_date": "2025-01-30",
      "broker_expected_by": "2025-01-31T08:00:00+00:00",
      "fx_delivery_id": "fx_rates-43dbf8fe9f4939cfee844e4f",
      "treasury_delivery_id": "treasury_rates-fb72a525531b06c98f3b9cb0",
      "fund_admin_delivery_id": "sim-admin-d4c87abd5740695f47b0bd8c",
      "bank_delivery_id": "sim-bank-8690941c886b2dc3602d214f",
      "bank_statement_date": "2025-02-07"
    }
    $$
AS
    EXECUTE DBT PROJECT NORTHBRIDGE_DEV.OPERATIONS.NORTHBRIDGE_DBT
        ARGS = 'build --target prod --exclude tag:fixture'
        WRITEBACK = FALSE
        ENV_VARS = (
          'DBT_CORPORATE_ACTION_LOAD_ID' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'corporate_action_load_id\')::string }}',
          'DBT_REPLAY_DELIVERY_ID' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'replay_delivery_id\')::string }}',
          'DBT_REPLAY_SCENARIO_ID' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'replay_scenario_id\')::string }}',
          'DBT_HISTORICAL_PRICE_DELIVERY_ID' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'historical_price_delivery_id\')::string }}',
          'DBT_BROKER_DELIVERY_ID' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'broker_delivery_id\')::string }}',
          'DBT_BROKER_STATEMENT_DATE' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'broker_statement_date\')::string }}',
          'DBT_BROKER_EXPECTED_BY' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'broker_expected_by\')::string }}',
          'DBT_FX_DELIVERY_ID' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'fx_delivery_id\')::string }}',
          'DBT_TREASURY_DELIVERY_ID' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'treasury_delivery_id\')::string }}',
          'DBT_FUND_ADMIN_DELIVERY_ID' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'fund_admin_delivery_id\')::string }}',
          'DBT_BANK_DELIVERY_ID' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'bank_delivery_id\')::string }}',
          'DBT_BANK_STATEMENT_DATE' = '{{ select SYSTEM$GET_TASK_GRAPH_CONFIG(\'bank_statement_date\')::string }}'
        );

CREATE OR ALTER TASK NORTHBRIDGE_DEV.OPERATIONS.DAILY_CLOSE_AUDIT
    WAREHOUSE = COMPUTE_WH
    AFTER NORTHBRIDGE_DEV.OPERATIONS.DAILY_CLOSE
AS
    INSERT INTO NORTHBRIDGE_DEV.OPERATIONS.TASK_RUN_AUDIT
        (audit_id, task_name, event_type, business_date)
    SELECT UUID_STRING(), 'DAILY_CLOSE', 'DBT_BUILD_SUCCEEDED',
           SYSTEM$GET_TASK_GRAPH_CONFIG('business_date')::string::date;

-- Deployment leaves the recurring root suspended. Operations enables it later.
ALTER TASK NORTHBRIDGE_DEV.OPERATIONS.DAILY_CLOSE_AUDIT SUSPEND;
ALTER TASK NORTHBRIDGE_DEV.OPERATIONS.DAILY_CLOSE SUSPEND;

SHOW TASKS IN SCHEMA NORTHBRIDGE_DEV.OPERATIONS;
