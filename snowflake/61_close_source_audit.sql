-- Read-only RAW and receipt audit for the 22 September pilot close.
-- Compare its delivery IDs and counts with the local inventory JSON.
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

WITH raw_rows AS (
    SELECT 'oms_events' AS source_name, delivery_id, COUNT(*) AS raw_rows
    FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
    WHERE scenario_id = 'sim-equity-2024-2026-v2'
      AND TRY_TO_DATE(payload:business_date::VARCHAR) <= '2026-09-22'
    GROUP BY delivery_id

    UNION ALL
    SELECT 'settlement_events', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS
    WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2'
      AND TRY_TO_DATE(payload:settlement_date::VARCHAR) <= '2026-09-22'
    GROUP BY delivery_id

    UNION ALL
    SELECT 'historical_prices', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
    WHERE delivery_id = 'fb25ddd9838840488e4c8b971ff7e0ae'
    GROUP BY delivery_id

    UNION ALL
    SELECT 'daily_prices', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
    WHERE valuation_date = '2026-09-22'
    GROUP BY delivery_id

    UNION ALL
    SELECT 'fund_admin', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.FUND_ADMIN_EVENTS
    WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2'
      AND TRY_TO_DATE(payload:event_date::VARCHAR) <= '2026-09-22'
    GROUP BY delivery_id

    UNION ALL
    SELECT 'dividend_payments', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.DIVIDEND_PAYMENT_EVENTS
    WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2'
      AND TRY_TO_DATE(payload:settlement_date::VARCHAR) <= '2026-09-22'
    GROUP BY delivery_id

    UNION ALL
    SELECT 'corporate_actions', load_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.CORPORATE_ACTIONS
    WHERE load_id = '890be0cfdcf2151ebb4aab47f0d53cd9'
    GROUP BY load_id

    UNION ALL
    SELECT 'corporate_action_reviews', load_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.CORPORATE_ACTION_REVIEWS
    WHERE load_id = '890be0cfdcf2151ebb4aab47f0d53cd9'
    GROUP BY load_id
),
receipts AS (
    SELECT source_name, delivery_id, COUNT(*) AS receipt_rows,
           MIN(manifest_sha256) AS receipt_sha256,
           MIN(expected_rows) AS expected_rows,
           MIN(received_rows) AS received_rows,
           MIN(delivery_status) AS delivery_status
    FROM NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
    GROUP BY source_name, delivery_id
)
SELECT r.source_name, r.delivery_id, r.raw_rows,
       x.receipt_rows, x.receipt_sha256, x.expected_rows,
       x.received_rows, x.delivery_status,
       CASE
           WHEN x.receipt_rows IS NULL THEN 'NO_RECEIPT'
           WHEN x.receipt_rows <> 1 THEN 'DUPLICATE_RECEIPT'
           WHEN x.delivery_status <> 'READY' THEN 'NOT_READY'
           WHEN x.expected_rows <> r.raw_rows OR x.received_rows <> r.raw_rows
               THEN 'COUNT_MISMATCH'
           ELSE 'COUNT_MATCH'
       END AS audit_result
FROM raw_rows r
LEFT JOIN receipts x
  ON r.source_name = x.source_name AND r.delivery_id = x.delivery_id
ORDER BY r.source_name, r.delivery_id;
