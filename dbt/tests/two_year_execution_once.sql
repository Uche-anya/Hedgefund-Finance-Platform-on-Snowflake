-- This scenario has one active trade and one settlement per execution ID.
-- If a corrected trade is introduced later, it needs an explicit version rule.
with trades as (
    select scenario_id, account_id, execution_id, count(*) as records
    from {{ ref('stg_oms_events') }}
    where scenario_id = '{{ var("scenario_id") }}'
      and execution_status = 'ACTIVE'
    group by 1, 2, 3
), settlements as (
    select scenario_id, account_id, execution_id, count(*) as records
    from {{ ref('stg_settlement_events') }}
    where scenario_id = '{{ var("scenario_id") }}'
      and settlement_status = 'SETTLED'
    group by 1, 2, 3
)
select 'OMS' as source_name, scenario_id, account_id, execution_id, records
from trades where execution_id is null or records <> 1
union all
select 'SETTLEMENT', scenario_id, account_id, execution_id, records
from settlements where execution_id is null or records <> 1
