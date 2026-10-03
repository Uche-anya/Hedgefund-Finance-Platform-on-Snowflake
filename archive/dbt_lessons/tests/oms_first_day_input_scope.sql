-- Do not apply the zero-opening assumption to a different scenario or day.
-- This test runs on the parent before dbt builds the positions table.
select *
from {{ ref('stg_oms_executions') }}
where scenario_id <> 'sim-historical-f9b72e1aa20041068cea4d5ac0b2eaf8'

      or business_date <> '2025-01-06'::date

      or fund_id <> 'NORTHBRIDGE'

      or account_id <> 'SIM-ACCOUNT-01'
