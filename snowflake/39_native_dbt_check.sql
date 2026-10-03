-- Prove the deployed project can build inside Snowflake without local Python.
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

EXECUTE DBT PROJECT NORTHBRIDGE_DEV.OPERATIONS.NORTHBRIDGE_DBT
    ARGS = 'build --target prod --exclude tag:fixture'
    WRITEBACK = FALSE;
