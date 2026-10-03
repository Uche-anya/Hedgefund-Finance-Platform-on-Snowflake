with sessions as (
    select distinct business_date from {{ ref('stg_activity_events') }} where record_type = 'SESSION'
),
fx as (
    select rate_date, count(*) as rows_found from {{ ref('stg_fx_rates') }} group by rate_date
),
treasury as (
    select rate_date, count(*) as rows_found from {{ ref('stg_treasury_rates') }} group by rate_date
)
select s.business_date
from sessions s
left join fx on s.business_date = fx.rate_date
left join treasury on s.business_date = treasury.rate_date
where coalesce(fx.rows_found, 0) <> 1 or coalesce(treasury.rows_found, 0) <> 1

union all

select rate_date from {{ ref('stg_fx_rates') }}
where base_currency <> 'EUR' or usd_per_eur <= 0 or gbp_per_eur <= 0 or source_system <> 'ECB_EXR'

union all

select rate_date from {{ ref('stg_treasury_rates') }}
where tenor <> '1M' or annual_rate_percent < 0 or day_count_basis <> 360
   or source_system <> 'US_TREASURY'
