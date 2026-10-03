-- Remove exact business-record repeats within this delivery.
-- Different records with the same execution ID remain and fail the unique test.
with received as (
    select distinct
        business_date as business_date_raw,
        execution_id,
        instrument,
        side,
        quantity as quantity_raw
    from {{ source('raw', 'executions') }}
    where source_system = 'simulated_oms'
      and delivery_id = '{{ var("delivery_id") }}'
)
select
    business_date_raw,
    try_to_date(business_date_raw, 'YYYY-MM-DD') as business_date,
    execution_id,
    instrument,
    side,
    quantity_raw,
    -- Reject excess precision instead of silently rounding share quantities.
    case when regexp_like(quantity_raw, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(quantity_raw, 38, 9)
    end as quantity
from received
