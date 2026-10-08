-- Read-only comparison with ledger 003's saved local reporting extract.
SELECT COUNT(*) AS account_days, MIN(business_date) AS first_day,
       MAX(business_date) AS last_day,
       SUM(reviewed_nav_usd) AS total_account_day_nav,
       SUM(net_market_value_usd) AS total_account_day_market_value
FROM NORTHBRIDGE_DEV.DBT_DEV.CMP_PYTHON_ACCOUNT_DAY
WHERE ledger_id = 'TWO_YEAR_REVIEW_003';

SELECT COUNT(*) AS position_days,
       SUM(market_value_usd) AS total_position_day_market_value
FROM NORTHBRIDGE_DEV.DBT_DEV.CMP_PYTHON_POSITION_DAY
WHERE ledger_id = 'TWO_YEAR_REVIEW_003';
