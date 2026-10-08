-- Read-only check before extending the two-year close beyond its saved history.
-- Change target_day after the next price and event deliveries arrive.
SET target_day = '2026-09-22';
SET due_day = '2026-09-23';

WITH traded_tickers AS (
    SELECT DISTINCT payload:market_ticker::VARCHAR AS ticker
    FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
    WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2'
), prices AS (
    SELECT COUNT(DISTINCT universe_ticker) AS priced_tickers
    FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
    WHERE valuation_date = $target_day
      AND universe_ticker IN (SELECT ticker FROM traded_tickers)
), oms AS (
    SELECT COUNT(*) AS executions, COUNT(DISTINCT delivery_id) AS deliveries
    FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
    WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2'
      AND payload:business_date::VARCHAR = $target_day
), settlements AS (
    SELECT COUNT(*) AS confirmations, COUNT(DISTINCT delivery_id) AS deliveries
    FROM NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS
    WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2'
      AND payload:settlement_date::VARCHAR = $target_day
), due_trades AS (
    SELECT COUNT(*) AS executions_due
    FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
    WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2'
      AND payload:settlement_due::VARCHAR = $target_day
)
SELECT $target_day AS target_day,
       (SELECT COUNT(*) FROM traded_tickers) AS required_tickers,
       prices.priced_tickers,
       oms.executions AS oms_rows,
       oms.deliveries AS oms_deliveries,
       due_trades.executions_due,
       settlements.confirmations AS settlement_rows,
       settlements.deliveries AS settlement_deliveries
FROM prices CROSS JOIN oms CROSS JOIN due_trades CROSS JOIN settlements;

SELECT $due_day AS due_day,
       (SELECT COUNT(*) FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
        WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2'
          AND payload:settlement_due::VARCHAR = $due_day) AS executions_due,
       (SELECT COUNT(*) FROM NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS
        WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2'
          AND payload:settlement_date::VARCHAR = $due_day) AS confirmations;

SELECT 'PRICES' AS feed, MAX(TRY_TO_DATE(valuation_date)) AS last_day
FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
UNION ALL
SELECT 'OMS', MAX(TRY_TO_DATE(payload:business_date::VARCHAR))
FROM NORTHBRIDGE_DEV.RAW.OMS_EVENTS
WHERE scenario_id = 'sim-equity-2024-2026-v2'
UNION ALL
SELECT 'SETTLEMENT', MAX(TRY_TO_DATE(payload:settlement_date::VARCHAR))
FROM NORTHBRIDGE_DEV.RAW.SETTLEMENT_EVENTS
WHERE payload:scenario_id::VARCHAR = 'sim-equity-2024-2026-v2';
