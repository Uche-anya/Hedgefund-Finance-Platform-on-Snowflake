-- First-day holdings only: opening positions are explicitly zero.
select
    a.business_date,
    a.portfolio,
    e.instrument,
    sum(case
        when e.side = 'BUY' then a.quantity
        when e.side = 'SELL' then -a.quantity
    end) as quantity
from {{ ref('stg_allocations') }} a
join {{ ref('stg_executions') }} e
    on a.execution_id = e.execution_id
    and a.business_date = e.business_date
group by a.business_date, a.portfolio, e.instrument
