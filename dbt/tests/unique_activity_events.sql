select
    event_id,
    count(*) as rows_received
from {{ ref('stg_activity_events') }}
where event_id is not null
group by event_id
having count(*) > 1
