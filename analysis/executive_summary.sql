-- Compact account-level summary for management review.
use role NORTHBRIDGE_DBT_DEV;
use warehouse COMPUTE_WH;
use database NORTHBRIDGE_DEV;
use schema DBT_DEV;

with nav_series as (
    select
        business_date,
        account_id,
        simplified_nav,
        investor_flows - lag(investor_flows, 1, 0) over (
            partition by account_id order by business_date
        ) as daily_external_flow,
        lag(simplified_nav) over (
            partition by account_id order by business_date
        ) as prior_nav
    from fct_daily_nav
),
daily_returns as (
    select
        *,
        (simplified_nav - prior_nav - daily_external_flow)
            / nullif(prior_nav, 0) as daily_return
    from nav_series
),
wealth as (
    select
        *,
        exp(sum(ln(1 + daily_return)) over (
            partition by account_id order by business_date
            rows between unbounded preceding and current row
        )) as wealth_index
    from daily_returns
    where daily_return is not null
),
drawdowns as (
    select
        *,
        wealth_index / max(wealth_index) over (
            partition by account_id order by business_date
            rows between unbounded preceding and current row
        ) - 1 as drawdown
    from wealth
),
performance as (
    select
        account_id,
        max_by(simplified_nav, business_date) as ending_nav,
        max_by(wealth_index, business_date) - 1 as cumulative_return,
        min(daily_return) as worst_day,
        max(daily_return) as best_day,
        min(drawdown) as maximum_drawdown,
        stddev_samp(daily_return) * sqrt(252) as indicative_annualised_volatility
    from drawdowns
    group by account_id
),
latest_day as (
    select max(business_date) as business_date from fct_daily_nav
),
latest_exposure as (
    select
        n.account_id,
        n.gross_exposure / nullif(n.simplified_nav, 0) as gross_exposure_pct,
        n.net_market_value / nullif(n.simplified_nav, 0) as net_exposure_pct,
        n.reported_settled_cash / nullif(n.simplified_nav, 0) as cash_pct,
        n.unconfirmed_due_trades
    from fct_daily_nav n
    join latest_day d on n.business_date = d.business_date
),
weights as (
    select
        v.account_id,
        v.market_ticker,
        abs(v.market_value) / nullif(sum(abs(v.market_value)) over (
            partition by v.account_id
        ), 0) as gross_weight
    from fct_daily_valuations v
    join latest_day d on v.business_date = d.business_date
    where v.closing_quantity <> 0
),
ranked_weights as (
    select
        *,
        row_number() over (
            partition by account_id order by gross_weight desc, market_ticker
        ) as weight_rank
    from weights
),
concentration as (
    select
        account_id,
        max_by(market_ticker, gross_weight) as largest_position,
        max(gross_weight) as largest_position_pct,
        sum(case when weight_rank <= 5 then gross_weight else 0 end) as top_five_pct,
        sum(gross_weight * gross_weight) as hhi_concentration
    from ranked_weights
    group by account_id
),
latest_settlement as (
    select
        s.account_id,
        count_if(s.settlement_status = 'NO_CONFIRMATION') as overdue_trades,
        sum(case when s.settlement_status = 'NO_CONFIRMATION'
                 then abs(s.outstanding_cash) else 0 end) as overdue_cash_exposure
    from fct_settlement_obligations s
    join latest_day d on s.business_date = d.business_date
    group by s.account_id
)
select
    p.account_id,
    p.ending_nav,
    p.cumulative_return,
    p.worst_day,
    p.best_day,
    p.maximum_drawdown,
    p.indicative_annualised_volatility,
    e.gross_exposure_pct,
    e.net_exposure_pct,
    e.cash_pct,
    c.largest_position,
    c.largest_position_pct,
    c.top_five_pct,
    c.hhi_concentration,
    s.overdue_trades,
    s.overdue_cash_exposure
from performance p
join latest_exposure e on p.account_id = e.account_id
join concentration c on p.account_id = c.account_id
join latest_settlement s on p.account_id = s.account_id
order by p.account_id;

select
    count_if(book_status = 'QUANTITY_MISMATCH') as quantity_mismatches,
    count_if(book_status = 'MISSING_AT_BROKER') as missing_at_broker,
    count_if(book_status = 'UNEXPECTED_AT_BROKER') as unexpected_at_broker,
    count_if(timeliness_status = 'LATE') as late_position_rows
from fct_position_reconciliation;

select
    count_if(reconciliation_status <> 'MATCHED') as bank_breaks,
    sum(case when reconciliation_status <> 'MATCHED'
             then abs(balance_difference) else 0 end) as bank_break_amount
from fct_bank_cash_reconciliation;
