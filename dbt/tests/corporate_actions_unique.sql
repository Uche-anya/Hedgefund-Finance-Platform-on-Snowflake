select
    event_id,
    count(*) as records
from {{ ref('stg_corporate_actions') }}
group by event_id
having event_id is null
   or count(*) <> 1
