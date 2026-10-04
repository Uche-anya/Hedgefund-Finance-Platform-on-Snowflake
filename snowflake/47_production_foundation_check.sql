-- Read-only check after Terraform creates the production foundations.
USE ROLE ACCOUNTADMIN;

SHOW DATABASES LIKE 'NORTHBRIDGE_PROD';

SHOW SCHEMAS IN DATABASE NORTHBRIDGE_PROD;

SHOW WAREHOUSES LIKE 'NORTHBRIDGE_PROD_WH';
SELECT
    "name",
    "state",
    "size",
    "auto_suspend",
    "resource_monitor",
    "enable_query_acceleration"
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

SHOW USERS LIKE 'NORTHBRIDGE_GITHUB_PROD_DEPLOY';
SELECT
    "name",
    "type",
    "disabled",
    "default_role",
    "default_warehouse",
    "default_secondary_roles"
FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));

SHOW GRANTS TO ROLE NORTHBRIDGE_DBT_PROD_DEPLOY;

SHOW GRANTS TO ROLE NORTHBRIDGE_DBT_PROD;
