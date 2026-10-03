select
    e.event_id as received_event,
    c.event_id as cash_event
from {{ ref('stg_oms_executions') }} e
full outer join {{ ref('oms_trade_cash') }} c
    on e.event_id = c.event_id
where e.event_id is null

      or c.event_id is null

      or e.execution_id <> c.execution_id

      or e.account_id <> c.account_id

      or e.currency <> c.currency

      or e.settlement_due <> c.settlement_due
