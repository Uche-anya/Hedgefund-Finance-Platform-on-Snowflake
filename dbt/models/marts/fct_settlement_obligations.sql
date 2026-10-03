with sessions as (
    select
        scenario_id,
        business_date,
        cutoff
    from {{ ref('stg_activity_events') }}
    where record_type = 'SESSION'
),

trades as (
    select
        *,
        quantity * execution_price * case when side = 'BUY' then -1 else 1 end as expected_cash
    from {{ ref('stg_activity_events') }}
    where record_type = 'EXECUTION'
),

settlements as (
    select *
    from {{ ref('stg_activity_events') }}
    where record_type = 'SETTLEMENT'
)
select
    d.scenario_id,
    d.business_date,
    d.cutoff,
    t.account_id,
    t.execution_id,
    t.instrument_id, t.currency, t.settlement_due, t.expected_cash,
    s.cash_amount as confirmed_cash,
    case when s.event_id is null then t.expected_cash else 0 end as outstanding_cash,
    case when s.event_id is not null then 'CONFIRMED'
         when t.settlement_due > d.business_date then 'NOT_DUE'
         else 'NO_CONFIRMATION' end as settlement_status
from sessions d join trades t
    on d.scenario_id = t.scenario_id and t.business_date <= d.business_date
    and t.published_at <= d.cutoff
left join settlements s
    on t.scenario_id = s.scenario_id and t.execution_id = s.execution_id
    and s.published_at <= d.cutoff and s.settled_at <= d.cutoff
