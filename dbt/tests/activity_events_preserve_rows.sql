with raw_rows as (
    select count(*) as n
    from {{ source('raw', 'replay_inputs') }}
    where delivery_id = '{{ var("replay_delivery_id") }}'
),

staged as (
    select count(*) as n
    from {{ ref('stg_activity_events') }}
)
select
    raw_rows.n,
    staged.n
from raw_rows cross join staged
where raw_rows.n = 0
   or raw_rows.n <> staged.n
