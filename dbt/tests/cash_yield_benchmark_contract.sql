with checked as (
    select *, count(*) over (
        partition by scenario_id, business_date, account_id, currency) as record_count
    from {{ ref('fct_cash_yield_benchmark') }}
)
select * from checked
where record_count <> 1
   or one_month_treasury_rate < 0 or day_count_basis <> 360
   or estimated_daily_interest is null
   or calculation_basis <> 'NON_ACCOUNTING_TREASURY_BENCHMARK'
