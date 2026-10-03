select
    try_to_date(payload:rate_date::varchar, 'YYYY-MM-DD') as rate_date,
    payload:tenor::varchar as tenor,
    try_to_decimal(payload:annual_rate_percent::varchar, 18, 9) as annual_rate_percent,
    try_to_number(payload:day_count_basis::varchar) as day_count_basis,
    payload:source_system::varchar as source_system,
    delivery_id,
    loaded_at
from {{ source('raw', 'treasury_rates') }}
where delivery_id = '{{ var("treasury_delivery_id") }}'
