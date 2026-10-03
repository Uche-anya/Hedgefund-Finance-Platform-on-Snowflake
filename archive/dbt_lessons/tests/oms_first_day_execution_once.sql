-- This lesson contains original fills only, one message per trade.
select
    scenario_id,
    execution_id,
    count(*) as messages
from {{ ref('stg_oms_executions') }}
group by scenario_id, execution_id
having count(*) > 1
