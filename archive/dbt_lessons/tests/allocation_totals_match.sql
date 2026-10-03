with allocated as (
    select
        business_date,
        execution_id,
        sum(quantity) as quantity
    from {{ ref('stg_allocations') }}
    group by business_date, execution_id
)
select
    e.execution_id,
    a.execution_id as allocated_execution_id,
    e.quantity as executed_quantity,
    a.quantity as allocated_quantity
from {{ ref('stg_executions') }} e
full outer join allocated a
    on e.execution_id = a.execution_id
    and e.business_date = a.business_date
where e.execution_id is null

      or a.execution_id is null

      or e.quantity <> a.quantity
