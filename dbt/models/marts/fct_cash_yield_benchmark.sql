-- An analytical estimate only. A Treasury yield is not proof of bank interest.
select
    c.scenario_id,
    c.business_date,
    c.account_id,
    c.currency,
    r.annual_rate_percent as one_month_treasury_rate,
    r.day_count_basis,
    c.reported_settled_cash * r.annual_rate_percent / 100 / r.day_count_basis
        as estimated_daily_interest,
    'NON_ACCOUNTING_TREASURY_BENCHMARK' as calculation_basis,
    r.delivery_id as treasury_delivery_id
from {{ ref('fct_daily_cash') }} c
join {{ ref('stg_treasury_rates') }} r on c.business_date = r.rate_date
where c.currency = 'USD' and r.tenor = '1M'
