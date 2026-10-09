select s.execution_id
from {{ ref('stg_settlements') }} s
left join {{ ref('stg_executions') }} e
    on e.execution_id = s.execution_id
    and e.account_id = s.account_id
    and e.scenario_id = s.scenario_id
where e.execution_id is null
   or e.execution_status <> 'ACTIVE'
   or s.settlement_date is null
   or s.settled_quantity is null
   or s.cash_amount is null
   or s.side is null
   or s.currency is null
   or s.settled_quantity <> e.quantity
   or s.cash_amount <> case
       when e.side = 'BUY' then -e.quantity * e.execution_price
       when e.side = 'SELL' then e.quantity * e.execution_price
   end
   or s.side <> e.side
   or s.currency <> e.currency
   or s.settlement_date < e.business_date
