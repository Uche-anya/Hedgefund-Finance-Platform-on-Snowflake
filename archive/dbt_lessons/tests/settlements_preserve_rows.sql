with received as (
    select count(*) as n
    from {{ source('raw', 'settlement_events') }}
    where delivery_id = '{{ var("settlement_delivery_id") }}'

          or delivery_id = '{{ var("settlement_late_delivery_id", "") }}'
),

staged as (
    select count(*) as n
    from {{ ref('stg_settlements') }}
)
select
    received.n,
    staged.n
from received cross join staged
where received.n = 0
   or received.n <> staged.n
