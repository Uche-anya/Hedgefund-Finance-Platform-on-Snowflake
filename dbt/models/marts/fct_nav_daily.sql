-- First NAV: USD equity positions plus modeled cash and unsettled trade cash.
{{ config(materialized='incremental', incremental_strategy='merge',
          unique_key=['valuation_date', 'scenario_id', 'account_id'],
          on_schema_change='append_new_columns') }}

with positions as (
    select valuation_date, scenario_id, account_id,
        sum(market_value) as position_value
    from {{ ref('fct_position_daily') }}
    where valuation_date = to_date('{{ var("business_date") }}')
      and scenario_id = '{{ var("scenario_id") }}'
    group by 1, 2, 3
)
select
    c.valuation_date,
    c.scenario_id,
    c.account_id,
    c.calculated_cash_balance,
    c.unsettled_trade_cash,
    coalesce(p.position_value, 0) as position_value,
    coalesce(v.dividend_receivable_usd, 0) as dividend_receivable_usd,
    coalesce(v.dividend_liability_usd, 0) as dividend_liability_usd,
    coalesce(v.dividend_pnl_usd, 0) as dividend_pnl_usd,
    c.calculated_cash_balance + c.unsettled_trade_cash
        + coalesce(p.position_value, 0)
        + coalesce(v.dividend_receivable_usd, 0)
        - coalesce(v.dividend_liability_usd, 0) as nav_usd
from {{ ref('fct_cash_daily') }} c
left join positions p
    on p.valuation_date = c.valuation_date
    and p.scenario_id = c.scenario_id
    and p.account_id = c.account_id
left join {{ ref('fct_dividend_daily') }} v
    on v.valuation_date = c.valuation_date
    and v.scenario_id = c.scenario_id
    and v.account_id = c.account_id
where c.valuation_date = to_date('{{ var("business_date") }}')
  and c.scenario_id = '{{ var("scenario_id") }}'
