-- Trade cash is owed from trade date; settlement moves it into modeled cash.
with days as (
    select distinct valuation_date
    from {{ ref('stg_prices') }}
), trades as (
    select
        scenario_id, account_id, execution_id, business_date,
        case
            when side = 'BUY' then -quantity * execution_price
            when side = 'SELL' then quantity * execution_price
        end as trade_cash
    from {{ ref('stg_executions') }}
    where execution_status = 'ACTIVE'
), cash_by_day as (
    select
        d.valuation_date,
        o.scenario_id,
        o.account_id,
        o.opening_cash,
        coalesce(sum(t.trade_cash), 0) as trade_cash_total,
        coalesce(sum(case
            when s.settlement_date <= d.valuation_date then s.cash_amount
            else 0
        end), 0) as settled_trade_cash
    from days d
    cross join {{ ref('stg_opening_cash') }} o
    left join trades t
        on t.account_id = o.account_id
        and t.scenario_id = o.scenario_id
        and t.business_date <= d.valuation_date
    left join {{ ref('stg_settlements') }} s
        on s.execution_id = t.execution_id
        and s.account_id = t.account_id
        and s.scenario_id = t.scenario_id
    group by 1, 2, 3, 4
)
select
    valuation_date,
    scenario_id,
    account_id,
    opening_cash,
    trade_cash_total,
    settled_trade_cash,
    opening_cash + settled_trade_cash as calculated_cash_balance,
    trade_cash_total - settled_trade_cash as unsettled_trade_cash
from cash_by_day
