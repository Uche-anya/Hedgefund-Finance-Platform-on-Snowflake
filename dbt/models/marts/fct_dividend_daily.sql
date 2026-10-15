-- A pay date moves the booked amount from receivable/liability to modeled cash.
-- Without a broker statement, this is a scenario calculation, not a receipt.
{{ config(materialized='incremental', incremental_strategy='merge',
          unique_key=['valuation_date', 'scenario_id', 'account_id']) }}

with days as (
    select distinct valuation_date
    from {{ ref('stg_prices') }}
    where valuation_date = to_date('{{ var("business_date") }}')
)
select
    d.valuation_date,
    e.scenario_id,
    e.account_id,
    sum(case when e.pay_date <= d.valuation_date
        then e.expected_cash_usd else 0 end) as modeled_dividend_cash_to_date,
    sum(case when e.pay_date > d.valuation_date and e.expected_cash_usd > 0
        then e.expected_cash_usd else 0 end) as dividend_receivable_usd,
    sum(case when e.pay_date > d.valuation_date and e.expected_cash_usd < 0
        then -e.expected_cash_usd else 0 end) as dividend_liability_usd,
    sum(case when e.ex_dividend_date = d.valuation_date
        then e.expected_cash_usd else 0 end) as dividend_pnl_usd
from days d
join {{ ref('fct_dividend_exposure') }} e
    on e.ex_dividend_date <= d.valuation_date
group by 1, 2, 3
