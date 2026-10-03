-- Measure the current workload before adding performance features.
-- This script changes no Snowflake objects.
USE ROLE SYSADMIN;
USE DATABASE NORTHBRIDGE_DEV;
USE WAREHOUSE COMPUTE_WH;

SHOW WAREHOUSES LIKE 'COMPUTE_WH';

SELECT
    table_schema,
    table_name,
    row_count,
    ROUND(bytes / 1024 / 1024, 2) AS storage_mb
FROM NORTHBRIDGE_DEV.INFORMATION_SCHEMA.TABLES
WHERE table_schema IN ('RAW', 'DBT_DEV')
ORDER BY bytes DESC, table_schema, table_name;

WITH recent_queries AS (
    SELECT
        COALESCE(NULLIF(query_tag, ''), 'UNTAGGED') AS query_tag,
        execution_status,
        total_elapsed_time,
        bytes_scanned,
        rows_produced
    FROM TABLE(NORTHBRIDGE_DEV.INFORMATION_SCHEMA.QUERY_HISTORY(
        END_TIME_RANGE_START => DATEADD('day', -6, CURRENT_TIMESTAMP()),
        RESULT_LIMIT => 10000
    ))
    WHERE database_name = 'NORTHBRIDGE_DEV'
      AND execution_status <> 'RUNNING'
)
SELECT
    query_tag,
    execution_status,
    COUNT(*) AS query_count,
    ROUND(AVG(total_elapsed_time) / 1000, 3) AS average_seconds,
    ROUND(MAX(total_elapsed_time) / 1000, 3) AS slowest_seconds,
    ROUND(SUM(bytes_scanned) / 1024 / 1024, 2) AS scanned_mb,
    SUM(rows_produced) AS rows_produced
FROM recent_queries
GROUP BY query_tag, execution_status
ORDER BY scanned_mb DESC, query_count DESC;
