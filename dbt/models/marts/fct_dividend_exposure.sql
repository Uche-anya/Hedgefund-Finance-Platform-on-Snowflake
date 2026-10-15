-- Book one entitlement per account on the ex-date. Later runs keep the row;
-- a provider correction needs a reviewed restatement, not a silent rewrite.
{{ config(materialized='incremental', incremental_strategy='merge',
          unique_key=['event_id', 'scenario_id', 'account_id']) }}

with events as (
    select *
    from {{ ref('dividend_review_queue') }}
    where processing_status = 'READY'
      and ex_dividend_date = to_date('{{ var("business_date") }}')
      and cash_amount > 0
      and currency = 'USD'
), prior_session as (
    select e.event_id, max(p.valuation_date) as valuation_date
    from events e
    join {{ ref('stg_prices') }} p
        on p.valuation_date < e.ex_dividend_date
    group by e.event_id
), validated as (
    select distinct business_date
    from {{ source('raw', 'daily_close_runs') }}
    where scenario_id = '{{ var("scenario_id") }}'
      and status = 'VALIDATED'
)
select
    e.event_id, e.terms_hash, e.instrument_id, e.ticker,
    e.ex_dividend_date, e.pay_date, s.valuation_date as eligible_close_date,
    p.scenario_id, p.account_id, p.shares as eligible_shares,
    e.cash_amount as cash_per_share_usd,
    p.shares * e.cash_amount as expected_cash_usd,
    case when p.shares < 0 then 'SHORT_PAYMENT_EXPOSURE'
         else 'LONG_RECEIVABLE' end as exposure_type,
    e.delivery_id as provider_delivery_id
from events e
join prior_session s on s.event_id = e.event_id
join validated v on v.business_date = s.valuation_date
join {{ ref('fct_position_daily') }} p
    on p.valuation_date = s.valuation_date
    and p.scenario_id = '{{ var("scenario_id") }}'
    and p.instrument_id = e.instrument_id
{% if is_incremental() %}
where not exists (
    select 1 from {{ this }} booked
    where booked.event_id = e.event_id
      and booked.scenario_id = p.scenario_id
      and booked.account_id = p.account_id
)
{% endif %}
