with received as (
    select distinct
        business_date as business_date_raw,
        allocation_id,
        execution_id,
        portfolio,
        quantity as quantity_raw
    from {{ source('raw', 'allocations') }}
    where source_system = 'simulated_oms'
      and delivery_id = '{{ var("delivery_id") }}'
)
select
    business_date_raw,
    try_to_date(business_date_raw, 'YYYY-MM-DD') as business_date,
    allocation_id,
    execution_id,
    portfolio,
    quantity_raw,
    case when regexp_like(quantity_raw, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(quantity_raw, 38, 9)
    end as quantity
from received
