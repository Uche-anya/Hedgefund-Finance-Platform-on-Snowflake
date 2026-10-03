with trades as (
    select *
    from {{ ref('stg_activity_events') }}
    where record_type = 'EXECUTION'
),

sessions as (
    select *
    from {{ ref('stg_activity_events') }}
    where record_type = 'SESSION'
),

accounts as (
    select *
    from {{ ref('stg_activity_events') }}
    where record_type = 'OPENING_CASH'
)
select t.event_id
from trades t
left join sessions s on t.scenario_id = s.scenario_id and t.business_date = s.business_date
left join accounts a on t.scenario_id = a.scenario_id and t.account_id = a.account_id
where s.business_date is null
   or a.account_id is null
   or t.published_at > s.cutoff
