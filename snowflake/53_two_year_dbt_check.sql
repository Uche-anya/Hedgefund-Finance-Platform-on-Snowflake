-- The new calculation reads the two-year source feeds, not the saved extract.
SELECT COUNT(*) AS account_days,
       MIN(business_date) AS first_day,
       MAX(business_date) AS last_day,
       SUM(reviewed_nav_usd) AS sum_of_daily_nav_for_load_check,
       SUM(net_market_value_usd) AS sum_of_daily_market_value
FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_NAV_DAILY
WHERE scenario_id = 'sim-equity-2024-2026-v2';

SELECT COUNT(*) AS position_days,
       SUM(market_value_usd) AS sum_of_position_market_value
FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_POSITIONS_DAILY
WHERE scenario_id = 'sim-equity-2024-2026-v2';
