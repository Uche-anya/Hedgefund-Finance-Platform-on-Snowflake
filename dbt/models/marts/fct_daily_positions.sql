with sessions as (
    select
        scenario_id,
        business_date
    from {{ ref('stg_activity_events') }}
    where record_type = 'SESSION'
),

trades as (
    select r.*, i.security_id
    from {{ ref('stg_activity_events') }} r
    join {{ ref('dim_instrument') }} i
      on r.market_ticker = i.ticker
     and r.business_date between i.valid_from and i.valid_to
    where r.record_type = 'EXECUTION'
),

instruments as (
    select
        distinct scenario_id,
        account_id,
        security_id,
        instrument_id,
        market_ticker,
        currency
    from trades
),

movements as (
    select
        scenario_id,
        account_id,
        security_id,
        instrument_id,
        business_date,
        sum(case when side = 'BUY' then quantity else -quantity end) as net_quantity,
        count(*) as trade_count
    from trades
    group by scenario_id, account_id, security_id, instrument_id, business_date
),

daily as (
    select
        s.business_date,
        i.*,
        coalesce(m.net_quantity, 0) as net_trade_quantity,
        coalesce(m.trade_count, 0) as trade_count
    from sessions s join instruments i on s.scenario_id = i.scenario_id
    left join movements m on i.scenario_id = m.scenario_id
        and i.account_id = m.account_id and i.security_id = m.security_id
        and s.business_date = m.business_date
)
select
    daily.*,
    coalesce(sum(net_trade_quantity) over (
        partition by scenario_id, account_id, security_id order by business_date
        rows between unbounded preceding and 1 preceding), 0) as opening_quantity,
    sum(net_trade_quantity) over (
        partition by scenario_id, account_id, security_id order by business_date
        rows between unbounded preceding and current row) as closing_quantity
from daily
