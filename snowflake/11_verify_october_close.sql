-- Check the October 12 delivery and its calculated close.
-- A VALIDATED run means the calculation passed; it is not NAV publication.
USE ROLE NORTHBRIDGE_DBT_DEV;

SELECT source_name, business_date, status, expected_rows, delivery_id
FROM NORTHBRIDGE_DEV.RAW.DAILY_DELIVERIES
WHERE (business_date = '2026-10-12' AND scenario_id IN ('massive', 'sim-close-20261008'))
   OR (business_date = '2026-10-07' AND scenario_id = 'sim-close-20261008'
       AND source_name IN ('opening_bank', 'opening_admin'))
ORDER BY business_date, source_name;

CALL NORTHBRIDGE_DEV.DBT_DEV.CHECK_DAILY_INPUTS(
    '2026-10-12'::date, 'sim-close-20261008', '2026-10-07'::date);

SELECT account_id, valuation_date, nav_usd
FROM NORTHBRIDGE_DEV.DBT_DEV.FCT_NAV_DAILY
WHERE valuation_date = '2026-10-12' AND scenario_id = 'sim-close-20261008'
ORDER BY account_id;

SELECT status, detail, started_at, finished_at
FROM NORTHBRIDGE_DEV.RAW.DAILY_CLOSE_RUNS
WHERE business_date = '2026-10-12' AND scenario_id = 'sim-close-20261008'
ORDER BY started_at DESC;
