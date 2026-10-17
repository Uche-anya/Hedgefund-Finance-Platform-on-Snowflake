-- Read-only evidence for the completed October 16 close.
-- The bank delivery on this date predates the transaction-ledger format.
USE ROLE SYSADMIN;

SELECT source_name, scenario_id, status, expected_rows, delivery_id
FROM NORTHBRIDGE_DEV.RAW.DAILY_DELIVERIES
WHERE business_date = '2026-10-16'
  AND source_name IN ('prices', 'dividends', 'oms', 'settlements', 'bank')
ORDER BY source_name;

SELECT d.source_name, d.expected_rows, COUNT(r.source_file) AS raw_rows
FROM NORTHBRIDGE_DEV.RAW.DAILY_DELIVERIES d
LEFT JOIN (
    SELECT 'bank' AS source_name, source_file
    FROM NORTHBRIDGE_DEV.RAW.DAILY_BANK_STATEMENTS
    UNION ALL
    SELECT 'dividends', source_file
    FROM NORTHBRIDGE_DEV.RAW.DAILY_DIVIDEND_EVENTS
    UNION ALL
    SELECT 'oms', source_file
    FROM NORTHBRIDGE_DEV.RAW.DAILY_OMS_EVENTS
    UNION ALL
    SELECT 'prices', source_file
    FROM NORTHBRIDGE_DEV.RAW.DAILY_PRICE_EVENTS
    UNION ALL
    SELECT 'settlements', source_file
    FROM NORTHBRIDGE_DEV.RAW.DAILY_SETTLEMENT_EVENTS
) r ON r.source_name = d.source_name
    AND ENDSWITH(r.source_file, d.stage_path)
WHERE d.business_date = '2026-10-16'
  AND d.source_name IN ('prices', 'dividends', 'oms', 'settlements', 'bank')
GROUP BY d.source_name, d.expected_rows
ORDER BY d.source_name;

SELECT status, COUNT(*) AS close_runs
FROM NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS
WHERE business_date = '2026-10-16'
  AND scenario_id = 'sim-close-20261008'
GROUP BY status;

SELECT account_id, nav_usd
FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_NAV_DAILY
WHERE valuation_date = '2026-10-16'
  AND scenario_id = 'sim-close-20261008'
ORDER BY account_id;

SELECT account_id, bank_cash, calculated_cash_balance, difference_usd,
    reconciliation_status
FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_CASH_RECONCILIATION
WHERE statement_date = '2026-10-16'
  AND scenario_id = 'sim-close-20261008'
ORDER BY account_id;
