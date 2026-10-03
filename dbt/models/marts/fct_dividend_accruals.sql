-- Only actions approved by operations can create an accounting entry.
with dividends as (
    select
        a.*,
        i.security_id,
        r.reviewed_record_date,
        r.review_id
    from {{ ref('stg_corporate_actions') }} a
    join {{ ref('approved_corporate_actions') }} r
      on a.event_id = r.event_id
    join {{ ref('dim_instrument') }} i
      on a.ticker = i.ticker
     and a.ex_dividend_date between i.valid_from and i.valid_to
    where a.action_type = 'dividends'
),

positions as (
    select *
    from {{ ref('fct_daily_positions') }}
)
select
    p.scenario_id,
    p.account_id,
    p.security_id,
    p.instrument_id,
    d.event_id,
    d.ex_dividend_date as accrual_date,
    d.record_date as provider_record_date,
    d.reviewed_record_date,
    d.pay_date as scheduled_pay_date,
    d.currency,
    p.opening_quantity as eligible_quantity,
    d.cash_amount as dividend_per_share,
    p.opening_quantity * d.cash_amount as expected_gross_amount,
    greatest(p.opening_quantity * d.cash_amount, 0) as dividend_receivable,
    greatest(-p.opening_quantity * d.cash_amount, 0) as short_dividend_payable,
    'GROSS_ENTITLEMENT_BEFORE_TAX' as calculation_basis,
    d.review_id,
    d.snapshot_id,
    d.load_id
from positions p
join dividends d
    on p.security_id = d.security_id
    and p.currency = d.currency
    and p.business_date = d.ex_dividend_date
