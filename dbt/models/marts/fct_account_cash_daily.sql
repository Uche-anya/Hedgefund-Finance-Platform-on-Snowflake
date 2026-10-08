-- Daily cash and open trade balances from separate OMS, custodian and admin feeds.
with days as (
    select business_date from {{ ref('int_market_days') }}
),
opening as (
    select payload:scenario_id::varchar as scenario_id,
           payload:account_id::varchar as account_id,
           try_to_date(payload:event_date::varchar) as opening_date,
           try_to_decimal(payload:amount::varchar, 38, 9) as opening_cash_usd
    from {{ source('raw', 'fund_admin_events') }} f
    where payload:scenario_id::varchar = '{{ var("scenario_id") }}'
      and payload:event_type::varchar = 'INVESTOR_SUBSCRIPTION'
      and payload:currency::varchar = 'USD'
      and {{ selected_delivery('fund_admin', 'f.delivery_id') }}
),
obligations as (
    select * from {{ ref('int_trade_obligations') }}
),
payments as (
    select payload:scenario_id::varchar as scenario_id,
           payload:account_id::varchar as account_id,
           try_to_date(payload:settlement_date::varchar) as payment_date,
           try_to_decimal(payload:cash_amount::varchar, 38, 9) as cash_amount
    from {{ source('raw', 'dividend_payment_events') }} p
    where payload:scenario_id::varchar = '{{ var("scenario_id") }}'
      and payload:event_type::varchar = 'DIVIDEND_PAYMENT_CONFIRMED'
      and {{ selected_delivery('dividend_payments', 'p.delivery_id') }}
),
account_days as (
    select o.scenario_id, o.account_id, d.business_date, o.opening_cash_usd
    from opening o cross join days d
    where d.business_date >= o.opening_date
),
trade_totals as (
    select d.scenario_id, d.account_id, d.business_date,
           sum(case when o.settlement_date <= d.business_date
                    then o.cash_amount else 0 end) as settled_trade_cash_usd,
           sum(case when o.business_date <= d.business_date
                     and (o.settlement_date > d.business_date or o.settlement_date is null)
                     and o.expected_cash_usd > 0
                    then o.expected_cash_usd else 0 end) as trade_receivable_usd,
           sum(case when o.business_date <= d.business_date
                     and (o.settlement_date > d.business_date or o.settlement_date is null)
                     and o.expected_cash_usd < 0
                    then -o.expected_cash_usd else 0 end) as trade_payable_usd
    from account_days d
    left join obligations o
      on d.scenario_id = o.scenario_id and d.account_id = o.account_id
    group by 1, 2, 3
),
payment_totals as (
    select d.scenario_id, d.account_id, d.business_date,
           sum(case when p.payment_date <= d.business_date
                    then p.cash_amount else 0 end) as confirmed_dividend_cash_usd
    from account_days d
    left join payments p
      on d.scenario_id = p.scenario_id and d.account_id = p.account_id
    group by 1, 2, 3
)
select d.scenario_id, d.business_date, d.account_id,
       d.opening_cash_usd + t.settled_trade_cash_usd
           + p.confirmed_dividend_cash_usd as settled_cash_usd,
       t.trade_receivable_usd, t.trade_payable_usd,
       p.confirmed_dividend_cash_usd
from account_days d
join trade_totals t
  on d.scenario_id = t.scenario_id and d.account_id = t.account_id
 and d.business_date = t.business_date
join payment_totals p
  on d.scenario_id = p.scenario_id and d.account_id = p.account_id
 and d.business_date = p.business_date
