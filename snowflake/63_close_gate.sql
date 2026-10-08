-- One technical gate for the selected two-year close inputs.
USE ROLE SYSADMIN;

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK (
    lock_name VARCHAR NOT NULL,
    touched_at TIMESTAMP_TZ
);

INSERT INTO NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK (lock_name)
SELECT 'DAILY_CLOSE'
WHERE NOT EXISTS (
    SELECT 1 FROM NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
    WHERE lock_name = 'DAILY_CLOSE'
);

CREATE OR REPLACE VIEW NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUT_AUDIT AS
WITH raw_rows AS (
    SELECT 'oms_events' AS source_name, delivery_id, COUNT(*) AS row_count
    FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS GROUP BY delivery_id
    UNION ALL
    SELECT 'settlement_events', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS GROUP BY delivery_id
    UNION ALL
    SELECT 'historical_prices', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES GROUP BY delivery_id
    UNION ALL
    SELECT 'daily_prices', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES GROUP BY delivery_id
    UNION ALL
    SELECT 'fund_admin', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.FUND_ADMIN_EVENTS GROUP BY delivery_id
    UNION ALL
    SELECT 'dividend_payments', delivery_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.DIVIDEND_PAYMENT_EVENTS GROUP BY delivery_id
    UNION ALL
    SELECT 'corporate_actions', load_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.CORPORATE_ACTIONS GROUP BY load_id
    UNION ALL
    SELECT 'corporate_action_reviews', load_id, COUNT(*)
    FROM NORTHBRIDGE_DEV.RAW.CORPORATE_ACTION_REVIEWS GROUP BY load_id
), receipts AS (
    SELECT source_name, delivery_id, COUNT(*) AS receipt_count,
           MIN(manifest_sha256) AS receipt_hash,
           MIN(expected_rows) AS expected_rows,
           MIN(received_rows) AS received_rows,
           MIN(delivery_status) AS delivery_status
    FROM NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
    GROUP BY source_name, delivery_id
)
SELECT i.request_id, i.source_name, i.delivery_id, i.expected_rows,
       COALESCE(r.row_count, 0) AS raw_rows,
       COALESCE(d.receipt_count, 0) AS receipt_count,
       i.evidence_status,
       CASE
         WHEN COALESCE(r.row_count, 0) <> i.expected_rows THEN 'BAD_RAW_COUNT'
         WHEN i.receipt_sha256 IS NULL AND i.evidence_status = 'LEGACY_RAW_COUNT_ONLY'
           THEN 'LEGACY_GAP'
         WHEN COALESCE(d.receipt_count, 0) <> 1 THEN 'BAD_RECEIPT_COUNT'
         WHEN d.receipt_hash <> i.receipt_sha256
           OR d.expected_rows <> i.expected_rows
           OR d.received_rows <> i.expected_rows
           OR d.delivery_status <> 'READY' THEN 'BAD_RECEIPT'
         ELSE 'VERIFIED'
       END AS input_status
FROM NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUTS i
LEFT JOIN raw_rows r
  ON i.source_name = r.source_name AND i.delivery_id = r.delivery_id
LEFT JOIN receipts d
  ON i.source_name = d.source_name AND i.delivery_id = d.delivery_id;

CREATE OR REPLACE VIEW NORTHBRIDGE_DEV.OPERATIONS.CLOSE_GATE AS
SELECT r.request_id, r.scenario_id, r.business_date, r.request_status,
       r.expected_input_count, COUNT(a.source_name) AS selected_inputs,
       COUNT_IF(a.input_status = 'VERIFIED') AS verified_inputs,
       COUNT_IF(a.input_status = 'LEGACY_GAP') AS legacy_gaps,
       COUNT_IF(a.input_status NOT IN ('VERIFIED', 'LEGACY_GAP')) AS bad_inputs,
       CASE WHEN r.request_status = 'CANDIDATE'
                 AND COUNT(a.source_name) = r.expected_input_count
                 AND COUNT_IF(a.input_status NOT IN ('VERIFIED', 'LEGACY_GAP')) = 0
            THEN 'BUILDABLE' ELSE 'BLOCKED' END AS build_gate,
       'NOT_APPROVED' AS publication_gate
FROM NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS r
LEFT JOIN NORTHBRIDGE_DEV.OPERATIONS.CLOSE_INPUT_AUDIT a
  ON r.request_id = a.request_id
GROUP BY r.request_id, r.scenario_id, r.business_date,
         r.request_status, r.expected_input_count;

-- This lock is held in a transaction while dbt runs. A second writer's UPDATE
-- times out; closing a failed connection rolls its lock transaction back.
