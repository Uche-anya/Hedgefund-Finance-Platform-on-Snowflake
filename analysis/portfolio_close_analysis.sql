-- Read-only analysis of the completed Northbridge development replay.
-- Amounts are USD. Returns are decimals: 0.01 means 1%.
use role NORTHBRIDGE_DBT_DEV;
use warehouse COMPUTE_WH;
use database NORTHBRIDGE_DEV;
use schema DBT_DEV;

-- 1. Latest account scorecard.
with latest_day as (
    select max(business_date) as business_date
    from fct_daily_nav
),
exposure as (
    select
        v.business_date,
        v.account_id,
        sum(case when v.market_value > 0 then v.market_value else 0 end) as long_exposure,
        abs(sum(case when v.market_value < 0 then v.market_value else 0 end)) as short_exposure,
        count_if(v.closing_quantity <> 0) as open_positions
    from fct_daily_valuations v
    join latest_day d on v.business_date = d.business_date
    group by v.business_date, v.account_id
)
select
    n.business_date,
    n.account_id,
    n.simplified_nav as nav,
    e.long_exposure,
    e.short_exposure,
    n.gross_exposure,
    n.net_market_value as net_exposure,
    e.long_exposure / nullif(n.simplified_nav, 0) as long_exposure_pct,
    e.short_exposure / nullif(n.simplified_nav, 0) as short_exposure_pct,
    n.gross_exposure / nullif(n.simplified_nav, 0) as gross_exposure_pct,
    n.net_market_value / nullif(n.simplified_nav, 0) as net_exposure_pct,
    n.reported_settled_cash / nullif(n.simplified_nav, 0) as cash_pct,
    e.open_positions,
    n.unconfirmed_due_trades
from fct_daily_nav n
join latest_day d on n.business_date = d.business_date
join exposure e
  on n.business_date = e.business_date and n.account_id = e.account_id
order by n.account_id;

-- 2. Daily performance after removing external investor flows.
-- investor_flows is cumulative in the accounting mart, so its daily change is
-- the amount that must be removed from the NAV movement.
with series as (
    select
        business_date,
        account_id,
        simplified_nav,
        investor_flows,
        lag(simplified_nav) over (
            partition by account_id order by business_date
        ) as prior_nav,
        investor_flows - lag(investor_flows, 1, 0) over (
            partition by account_id order by business_date
        ) as daily_external_flow
    from fct_daily_nav
),
returns as (
    select
        *,
        (simplified_nav - prior_nav - daily_external_flow)
            / nullif(prior_nav, 0) as daily_return
    from series
),
wealth as (
    select
        *,
        exp(sum(ln(1 + daily_return)) over (
            partition by account_id order by business_date
            rows between unbounded preceding and current row
        )) as wealth_index
    from returns
    where daily_return is not null
),
drawdown as (
    select
        *,
        max(wealth_index) over (
            partition by account_id order by business_date
            rows between unbounded preceding and current row
        ) as running_peak
    from wealth
)
select
    business_date,
    account_id,
    simplified_nav,
    daily_external_flow,
    daily_return,
    wealth_index - 1 as cumulative_return,
    wealth_index / nullif(running_peak, 0) - 1 as drawdown
from drawdown
order by account_id, business_date;

-- 3. Latest position concentration.
with latest_day as (
    select max(business_date) as business_date
    from fct_daily_valuations
),
positions as (
    select
        v.business_date,
        v.account_id,
        v.market_ticker,
        v.closing_quantity,
        v.market_value,
        abs(v.market_value) / nullif(sum(abs(v.market_value)) over (
            partition by v.business_date, v.account_id
        ), 0) as gross_weight
    from fct_daily_valuations v
    join latest_day d on v.business_date = d.business_date
    where v.closing_quantity <> 0
)
select
    *,
    dense_rank() over (
        partition by account_id order by gross_weight desc
    ) as concentration_rank,
    sum(gross_weight * gross_weight) over (
        partition by business_date, account_id
    ) as hhi_concentration
from positions
order by account_id, concentration_rank, market_ticker;

-- 4. Explain each daily NAV movement.
-- Price P&L measures yesterday's shares at today's price change.
-- Execution P&L measures today's trades against today's close.
-- The residual contains dividends, expenses and other accounting effects.
with valued as (
    select
        business_date,
        account_id,
        security_id,
        market_ticker,
        opening_quantity,
        close_price,
        lag(close_price) over (
            partition by account_id, security_id order by business_date
        ) as prior_close
    from fct_daily_valuations
),
price_pnl as (
    select
        business_date,
        account_id,
        sum(opening_quantity * (close_price - prior_close)) as price_move_pnl
    from valued
    group by business_date, account_id
),
execution_pnl as (
    select
        e.business_date,
        e.account_id,
        sum(case
            when e.side = 'BUY' then e.quantity * (v.close_price - e.execution_price)
            when e.side = 'SELL' then e.quantity * (e.execution_price - v.close_price)
        end) as execution_vs_close_pnl
    from stg_activity_events e
    join fct_daily_valuations v
      on e.scenario_id = v.scenario_id
     and e.business_date = v.business_date
     and e.account_id = v.account_id
     and e.instrument_id = v.instrument_id
    where e.record_type = 'EXECUTION'
    group by e.business_date, e.account_id
),
nav_change as (
    select
        business_date,
        account_id,
        simplified_nav,
        simplified_nav - lag(simplified_nav) over (
            partition by account_id order by business_date
        ) as reported_nav_change,
        investor_flows - lag(investor_flows, 1, 0) over (
            partition by account_id order by business_date
        ) as daily_external_flow
    from fct_daily_nav
)
select
    n.business_date,
    n.account_id,
    n.reported_nav_change,
    n.daily_external_flow,
    n.reported_nav_change - n.daily_external_flow as flow_adjusted_nav_change,
    coalesce(p.price_move_pnl, 0) as price_move_pnl,
    coalesce(e.execution_vs_close_pnl, 0) as execution_vs_close_pnl,
    n.reported_nav_change - n.daily_external_flow
        - coalesce(p.price_move_pnl, 0)
        - coalesce(e.execution_vs_close_pnl, 0) as other_pnl_and_accounting
from nav_change n
left join price_pnl p
  on n.business_date = p.business_date and n.account_id = p.account_id
left join execution_pnl e
  on n.business_date = e.business_date and n.account_id = e.account_id
where n.reported_nav_change is not null
order by n.account_id, n.business_date;

-- 5. Settlement quality by day.
select
    business_date,
    account_id,
    count(*) as obligations,
    count_if(settlement_status = 'CONFIRMED') as confirmed,
    count_if(settlement_status = 'NO_CONFIRMATION') as overdue_unconfirmed,
    count_if(settlement_status = 'NO_CONFIRMATION') / nullif(count(*), 0)
        as overdue_rate,
    sum(case when settlement_status = 'NO_CONFIRMATION'
             then abs(outstanding_cash) else 0 end) as overdue_cash_exposure
from fct_settlement_obligations
group by business_date, account_id
order by account_id, business_date;

-- 6. Independent statement breaks requiring investigation.
select
    'BROKER_POSITION' as control,
    statement_date,
    account_id,
    ticker as item,
    book_status as result,
    quantity_difference as difference,
    timeliness_status
from fct_position_reconciliation
where book_status <> 'MATCHED' or timeliness_status <> 'ON_TIME'
union all
select
    'BANK_CASH',
    statement_date,
    account_id,
    currency,
    reconciliation_status,
    balance_difference,
    null
from fct_bank_cash_reconciliation
where reconciliation_status <> 'MATCHED'
order by control, account_id, item;
