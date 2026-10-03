with checked as (
    select *, count(*) over (
        partition by scenario_id, business_date, account_id, reporting_currency) as record_count
    from {{ ref('fct_daily_nav_reporting') }}
)
select * from checked
where record_count <> 1
   or local_currency <> 'USD' or reporting_currency not in ('EUR', 'GBP')
   or reporting_rate <= 0 or reporting_nav is null
