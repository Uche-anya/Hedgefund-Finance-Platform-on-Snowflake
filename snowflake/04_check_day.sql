-- Change the two values below to inspect one saved day.
SET close_date = '2024-09-24';
SET close_scenario = 'sim-equity-2024-2026-v2';

-- SUBMITTED means Snowpipe accepted the file, not that rows are in RAW yet.
-- The actual count is the evidence of loading. Empty deliveries need no rows.
WITH expected_sources AS (
    SELECT 'oms' AS source_name, $close_scenario AS source_scenario
    UNION ALL
    SELECT 'settlements', $close_scenario
    UNION ALL
    SELECT 'prices', 'massive'
), loaded AS (
    SELECT 'oms' AS source_name, source_file, COUNT(*) AS row_count
    FROM NORTHBRIDGE_DEV.RAW.DAILY_OMS_EVENTS
    GROUP BY source_file
    UNION ALL
    SELECT 'settlements', source_file, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.DAILY_SETTLEMENT_EVENTS
    GROUP BY source_file
    UNION ALL
    SELECT 'prices', source_file, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.DAILY_PRICE_EVENTS
    GROUP BY source_file
)
SELECT
    e.source_name,
    d.delivery_id,
    d.status,
    d.expected_rows,
    COALESCE(SUM(l.row_count), 0) AS loaded_rows,
    CASE
        WHEN d.delivery_id IS NULL THEN 'MISSING'
        WHEN d.status = 'EMPTY' AND d.expected_rows = 0
             AND COALESCE(SUM(l.row_count), 0) = 0 THEN 'READY'
        WHEN d.status IN ('SUBMITTED', 'LOADED') AND d.expected_rows > 0
             AND COALESCE(SUM(l.row_count), 0) = d.expected_rows THEN 'READY'
        WHEN COALESCE(SUM(l.row_count), 0) > d.expected_rows THEN 'EXTRA_ROWS'
        ELSE 'WAITING'
    END AS load_state
FROM expected_sources e
LEFT JOIN NORTHBRIDGE_DEV.RAW.DAILY_DELIVERIES d
    ON d.source_name = e.source_name
   AND d.business_date = $close_date
   AND d.scenario_id = e.source_scenario
LEFT JOIN loaded l ON l.source_name = e.source_name
    AND ENDSWITH(l.source_file, d.stage_path)
GROUP BY e.source_name, d.delivery_id, d.status, d.expected_rows
ORDER BY e.source_name;

-- More than one row means the same delivery ID was registered twice.
SELECT delivery_id, COUNT(*) AS registry_rows
FROM NORTHBRIDGE_DEV.RAW.DAILY_DELIVERIES
GROUP BY delivery_id
HAVING COUNT(*) > 1;
