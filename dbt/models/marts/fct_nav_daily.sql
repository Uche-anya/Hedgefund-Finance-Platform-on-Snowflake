-- First NAV: USD equity positions plus modeled cash and unsettled trade cash.
with positions as (
    select valuation_date, scenario_id, account_id,
        sum(market_value) as position_value
    from {{ ref('fct_position_daily') }}
    group by 1, 2, 3
)
select
    c.valuation_date,
    c.scenario_id,
    c.account_id,
    c.calculated_cash_balance,
    c.unsettled_trade_cash,
    coalesce(p.position_value, 0) as position_value,
    c.calculated_cash_balance + c.unsettled_trade_cash
        + coalesce(p.position_value, 0) as nav_usd
from {{ ref('fct_cash_daily') }} c
left join positions p
    on p.valuation_date = c.valuation_date
    and p.scenario_id = c.scenario_id
    and p.account_id = c.account_id
