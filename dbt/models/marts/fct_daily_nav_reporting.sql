-- Translate the USD accounting NAV for reporting. ECB quotes currencies per EUR.
select
    n.scenario_id,
    n.business_date,
    n.account_id,
    n.currency as local_currency,
    target.reporting_currency,
    n.simplified_nav as local_nav,
    case target.reporting_currency
        when 'EUR' then 1 / r.usd_per_eur
        when 'GBP' then r.gbp_per_eur / r.usd_per_eur
    end as reporting_rate,
    n.simplified_nav * reporting_rate as reporting_nav,
    r.delivery_id as fx_delivery_id
from {{ ref('fct_daily_nav') }} n
join {{ ref('stg_fx_rates') }} r on n.business_date = r.rate_date
cross join (select 'EUR' as reporting_currency union all select 'GBP') target
where n.currency = 'USD'
