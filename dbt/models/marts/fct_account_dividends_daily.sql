-- Ex-date entitlement uses the shares held at the previous market close.
-- Only approved events enter reviewed NAV; other candidates stay separate.
with sessions as (
    select business_date from {{ ref('int_market_days') }}
),
dated_sessions as (
    select business_date,
           lag(business_date) over (order by business_date) as prior_market_day
    from sessions
),
actions as (
    select a.event_id, a.ticker, a.ex_dividend_date,
           s.prior_market_day, a.cash_amount,
           coalesce(d.decision, 'PENDING') as decision
    from {{ ref('stg_corporate_actions') }} a
    join dated_sessions s on a.ex_dividend_date = s.business_date
    left join {{ ref('reviewed_action_decisions') }} d
      on a.event_id = d.event_id
    where a.action_type = 'dividends' and a.currency = 'USD'
      and a.ticker in (select distinct ticker_as_of_date
                       from {{ ref('fct_account_positions_daily') }})
),
entitlements as (
    select a.event_id, a.ex_dividend_date, c.account_id, a.decision,
           coalesce(p.quantity, 0) * a.cash_amount as gross_amount_usd
    from actions a
    cross join (select distinct account_id
                from {{ ref('fct_account_cash_daily') }}) c
    left join {{ ref('fct_account_positions_daily') }} p
      on p.business_date = a.prior_market_day
     and p.account_id = c.account_id
     and p.ticker_as_of_date = a.ticker
),
payment_totals as (
    select d.business_date, d.account_id,
           sum(case when try_to_date(p.payload:settlement_date::varchar) <= d.business_date
                    then try_to_decimal(p.payload:cash_amount::varchar, 38, 9)
                    else 0 end) as confirmed_cash_usd
    from {{ ref('fct_account_cash_daily') }} d
    left join {{ source('raw', 'dividend_payment_events') }} p
      on p.payload:scenario_id::varchar = d.scenario_id
     and p.payload:account_id::varchar = d.account_id
     and p.payload:event_type::varchar = 'DIVIDEND_PAYMENT_CONFIRMED'
     and {{ selected_delivery('dividend_payments', 'p.delivery_id') }}
    group by 1, 2
),
accruals as (
    select d.scenario_id, d.business_date, d.account_id,
           sum(case when e.decision = 'APPROVE' and e.gross_amount_usd > 0
                    then e.gross_amount_usd else 0 end) as approved_long_usd,
           sum(case when e.decision = 'APPROVE' and e.gross_amount_usd < 0
                    then -e.gross_amount_usd else 0 end) as approved_short_usd,
           sum(case when e.decision <> 'APPROVE'
                    then e.gross_amount_usd else 0 end) as pending_candidate_impact_usd
    from {{ ref('fct_account_cash_daily') }} d
    left join entitlements e
      on e.account_id = d.account_id and e.ex_dividend_date <= d.business_date
    group by 1, 2, 3
)
select a.scenario_id, a.business_date, a.account_id,
       a.approved_long_usd - greatest(p.confirmed_cash_usd, 0)
           as reviewed_dividend_receivable_usd,
       a.approved_short_usd - greatest(-p.confirmed_cash_usd, 0)
           as reviewed_short_dividend_payable_usd,
       a.pending_candidate_impact_usd
from accruals a
join payment_totals p
  on a.business_date = p.business_date and a.account_id = p.account_id
