-- Every account we value needs a starting cash balance.
select distinct e.account_id
from {{ ref('stg_executions') }} e
left join {{ ref('stg_opening_cash') }} o
    on o.scenario_id = e.scenario_id
    and o.account_id = e.account_id
where e.execution_status = 'ACTIVE'
  and o.account_id is null
