-- A market delivery is shared by all simulated accounts.
select
    try_to_date(r.payload:valuation_date::varchar) as valuation_date,
    r.payload:universe_ticker::varchar as market_ticker,
    try_to_decimal(r.payload:close_price::varchar, 38, 9) as close_price,
    r.payload:currency::varchar as currency,
    r.payload:price_basis::varchar as price_basis,
    r.payload:source_system::varchar as source_system,
    r.source_file,
    r.source_row_number
from {{ source('raw', 'daily_price_events') }} r
join {{ source('raw', 'daily_deliveries') }} d
    on d.source_name = 'prices'
    and d.scenario_id = 'massive'
    and d.status = 'LOADED'
    and d.business_date >= to_date('{{ var("opening_date") }}')
    and d.business_date <= to_date('{{ var("business_date") }}')
    and endswith(r.source_file, d.stage_path)
