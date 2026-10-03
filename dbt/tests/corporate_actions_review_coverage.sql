-- Every source event must appear once or have a recorded exclusion.
with raw_events as (
    select payload:event:id::varchar as event_id
    from {{ source('raw', 'corporate_actions') }}
    where load_id = '{{ var("corporate_action_load_id") }}'
),

represented as (
    select f.value::varchar as event_id
    from {{ ref('stg_corporate_actions') }} s,
         lateral flatten(input => s.source_event_ids) f

    union all

    select payload:decision:event_id::varchar
    from {{ source('raw', 'corporate_action_reviews') }}
    where load_id = '{{ var("corporate_action_load_id") }}'
      and payload:decision:decision::varchar = 'EXCLUDED_FROM_BANK'
      and payload:decision:target_instrument::varchar = 'US_BNY_MELLON_COMMON'
),

counts as (
    select
        event_id,
        count(*) as n
    from represented
    group by event_id
)
select coalesce(r.event_id, c.event_id) as problem
from raw_events r full outer join counts c on r.event_id = c.event_id
where r.event_id is null
   or c.event_id is null
   or c.n <> 1
