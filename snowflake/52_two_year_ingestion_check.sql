-- Which two-year rows arrived through daily Snowpipe files, and which through
-- the compact historical backfill? File paths are retained in RAW.
SELECT 'OMS' AS feed,
       IFF(source_file LIKE '%backfill/%', 'BULK_BACKFILL', 'DAILY_FILE') AS route,
       COUNT(*) AS rows_loaded, COUNT(DISTINCT delivery_id) AS deliveries,
       MIN(TRY_TO_DATE(payload:business_date::varchar)) AS first_business_date,
       MAX(TRY_TO_DATE(payload:business_date::varchar)) AS last_business_date
FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
WHERE scenario_id = 'sim-equity-2024-2026-v2'
GROUP BY route
UNION ALL
SELECT 'SETTLEMENT',
       IFF(source_file LIKE '%backfill/%', 'BULK_BACKFILL', 'DAILY_FILE'),
       COUNT(*), COUNT(DISTINCT delivery_id),
       MIN(TRY_TO_DATE(payload:settlement_date::varchar)),
       MAX(TRY_TO_DATE(payload:settlement_date::varchar))
FROM NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS
WHERE payload:scenario_id::varchar = 'sim-equity-2024-2026-v2'
GROUP BY 2
ORDER BY feed, route;

SELECT source_file, delivery_id
FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
WHERE scenario_id = 'sim-equity-2024-2026-v2'
ORDER BY source_file
LIMIT 3;

SHOW PIPES LIKE '%EVENTS_PIPE' IN SCHEMA NORTHBRIDGE_DEV.RAW;
