with received as (
    select count(*) as row_count
    from {{ source('raw', 'oms_events') }}
    where delivery_id = '{{ var("oms_delivery_id") }}'
),

staged as (
    select count(*) as row_count
    from {{ ref('stg_oms_executions') }}
)
select
    received.row_count as received_rows,
    staged.row_count as staged_rows
from received cross join staged
where received.row_count = 0

      or received.row_count <> staged.row_count
