-- Each price date closes the position built from all executions through that day.
with days as (
    select distinct valuation_date
    from {{ ref('stg_prices') }}
), holdings as (
    select
        d.valuation_date,
        e.scenario_id,
        e.account_id,
        e.instrument_id,
        e.market_ticker,
        sum(case
            when e.execution_status = 'ACTIVE' and e.side = 'BUY' then e.quantity
            when e.execution_status = 'ACTIVE' and e.side = 'SELL' then -e.quantity
            else 0
        end) as shares
    from days d
    join {{ ref('stg_executions') }} e
        on e.business_date <= d.valuation_date
    group by 1, 2, 3, 4, 5
    having shares <> 0
)
select
    h.valuation_date,
    h.scenario_id,
    h.account_id,
    h.instrument_id,
    h.market_ticker,
    h.shares,
    p.close_price,
    p.currency,
    h.shares * p.close_price as market_value
from holdings h
left join {{ ref('stg_prices') }} p
    on p.valuation_date = h.valuation_date
    and p.market_ticker = h.market_ticker
