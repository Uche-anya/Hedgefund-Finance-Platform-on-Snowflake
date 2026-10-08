-- What arrived, and what did the new provisional close calculate?
SELECT source_name, delivery_id, expected_rows, received_rows, delivery_status
FROM NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
WHERE delivery_id IN (
    'daily-prices-f2d7bf4ad3d75d9c8b1b772e',
    'oms-sim-equity-2024-2026-v2-20260922',
    'settlement-sim-equity-2024-2026-v2-20260923'
)
ORDER BY source_name;

SELECT business_date, account_id, settled_cash_usd,
       trade_receivable_usd, trade_payable_usd,
       net_market_value_usd, reviewed_nav_usd, nav_status
FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_NAV_DAILY
WHERE scenario_id = 'sim-equity-2024-2026-v2'
  AND business_date IN ('2026-09-21', '2026-09-22')
ORDER BY business_date, account_id;

SELECT 'OMS_2026_09_22' AS check_name, COUNT(*) AS rows_found
FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
WHERE delivery_id = 'oms-sim-equity-2024-2026-v2-20260922'
UNION ALL
SELECT 'SETTLEMENT_2026_09_23', COUNT(*)
FROM NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS
WHERE delivery_id = 'settlement-sim-equity-2024-2026-v2-20260923'
UNION ALL
SELECT 'PRICE_2026_09_22', COUNT(*)
FROM NORTHBRIDGE_DEV.DBT_DEV.STG_HISTORICAL_PRICES
WHERE valuation_date = '2026-09-22'
UNION ALL
SELECT 'NAV_2026_09_22', COUNT(*)
FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_NAV_DAILY
WHERE business_date = '2026-09-22'
  AND scenario_id = 'sim-equity-2024-2026-v2';
