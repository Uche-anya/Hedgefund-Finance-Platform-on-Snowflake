-- Check that the deployed project can rebuild the pinned development close.
-- This writes the shared DBT_DEV models. The saved candidate stays separate.
USE ROLE SYSADMIN;

EXECUTE DBT PROJECT NORTHBRIDGE_DEV.OPERATIONS.NORTHBRIDGE_DBT
    ARGS = 'build --select +fct_account_nav_daily --exclude tag:fixture --target dev --vars "close_request_id: 5d1f1abedf4cbe14e6a6cef3"'
    ENVIRONMENT = 'dev';
