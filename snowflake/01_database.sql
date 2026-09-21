-- Run in Snowsight, in order. Live execution is not yet verified.
-- SYSADMIN owns this initial development database.
USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS NORTHBRIDGE_DEV;
CREATE SCHEMA IF NOT EXISTS NORTHBRIDGE_DEV.RAW;

USE DATABASE NORTHBRIDGE_DEV;
USE SCHEMA RAW;

SELECT
    CURRENT_ROLE() AS active_role,
    CURRENT_DATABASE() AS active_database,
    CURRENT_SCHEMA() AS active_schema;
