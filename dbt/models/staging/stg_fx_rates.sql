select
    try_to_date(payload:rate_date::varchar, 'YYYY-MM-DD') as rate_date,
    payload:base_currency::varchar as base_currency,
    try_to_decimal(payload:usd_per_eur::varchar, 38, 12) as usd_per_eur,
    try_to_decimal(payload:gbp_per_eur::varchar, 38, 12) as gbp_per_eur,
    payload:source_system::varchar as source_system,
    delivery_id,
    loaded_at
from {{ source('raw', 'fx_rates') }}
where delivery_id = '{{ var("fx_delivery_id") }}'
