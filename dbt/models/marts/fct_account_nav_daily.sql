-- Provisional NAV rebuilt in Snowflake from the two-year event feeds.
with positions as (
    select scenario_id, business_date, account_id,
           sum(market_value_usd) as net_market_value_usd,
           sum(case when market_value_usd > 0 then market_value_usd else 0 end)
               as long_market_value_usd,
           sum(case when market_value_usd < 0 then -market_value_usd else 0 end)
               as short_market_value_abs_usd
    from {{ ref('fct_account_positions_daily') }}
    group by 1, 2, 3
),
balances as (
    select c.scenario_id, c.business_date, c.account_id,
           c.settled_cash_usd, c.trade_receivable_usd, c.trade_payable_usd,
           coalesce(p.net_market_value_usd, 0) as net_market_value_usd,
           coalesce(p.long_market_value_usd, 0) as long_market_value_usd,
           coalesce(p.short_market_value_abs_usd, 0) as short_market_value_abs_usd,
           d.reviewed_dividend_receivable_usd,
           d.reviewed_short_dividend_payable_usd,
           d.pending_candidate_impact_usd
    from {{ ref('fct_account_cash_daily') }} c
    left join positions p
      on c.scenario_id = p.scenario_id and c.business_date = p.business_date
     and c.account_id = p.account_id
    join {{ ref('fct_account_dividends_daily') }} d
      on c.scenario_id = d.scenario_id and c.business_date = d.business_date
     and c.account_id = d.account_id
)
select *,
       'EXPLORATORY_PROVISIONAL' as nav_status,
       settled_cash_usd + trade_receivable_usd - trade_payable_usd
           + net_market_value_usd + reviewed_dividend_receivable_usd
           - reviewed_short_dividend_payable_usd as reviewed_nav_usd,
       settled_cash_usd + trade_receivable_usd - trade_payable_usd
           + net_market_value_usd + reviewed_dividend_receivable_usd
           - reviewed_short_dividend_payable_usd
           + pending_candidate_impact_usd as illustrative_nav_usd
from balances
