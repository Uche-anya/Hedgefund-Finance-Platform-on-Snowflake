with raw_count as (
    select count(*) as records
    from {{ source('raw', 'historical_prices') }}
    where delivery_id = '{{ var("historical_price_delivery_id") }}'
),

staged_count as (
    select count(*) as records
    from {{ ref('stg_historical_prices') }}
)
select
    raw_count.records as raw_records,
    staged_count.records as staged_records
from raw_count cross join staged_count
where raw_count.records = 0
   or raw_count.records <> staged_count.records
