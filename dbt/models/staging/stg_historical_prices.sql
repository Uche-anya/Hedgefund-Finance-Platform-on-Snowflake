-- Keep all received rows so duplicate or conflicting records fail tests.
select
    valuation_date as valuation_date_raw,
    try_to_date(valuation_date, 'YYYY-MM-DD') as valuation_date,
    universe_ticker,
    nullif(instrument_id, '') as instrument_id,
    nullif(share_class_figi, '') as share_class_figi,
    source_ticker,
    currency,
    open_price as open_price_raw,
    case when regexp_like(open_price, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(open_price, 38, 9) end as open_price,
    high_price as high_price_raw,
    case when regexp_like(high_price, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(high_price, 38, 9) end as high_price,
    low_price as low_price_raw,
    case when regexp_like(low_price, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(low_price, 38, 9) end as low_price,
    close_price as close_price_raw,
    case when regexp_like(close_price, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(close_price, 38, 9) end as close_price,
    volume as volume_raw,
    -- The saved provider bars include values such as 2.17948E+6.
    -- Positive exponents do not add fractional places beyond the nine allowed.
    case when regexp_like(volume, '^[0-9]{1,29}([.][0-9]{1,9})?([eE][+]?[0-9]{1,2})?$')
        then try_to_decimal(volume, 38, 9) end as volume,
    price_basis,
    identity_status,
    source_system,
    delivery_id,
    input_file,
    input_row_number as input_row_number_raw,
    case when regexp_like(input_row_number, '^[0-9]{1,38}$')
        then try_to_number(input_row_number, 38, 0) end as input_row_number,
    source_file,
    source_row_number,
    loaded_at
from {{ source('raw', 'historical_prices') }} raw
{% if var('close_request_id', '') %}
where {{ selected_delivery('historical_prices', 'raw.delivery_id') }}
   or {{ selected_delivery('daily_prices', 'raw.delivery_id') }}
{% elif target.name == 'prod' %}
    {{ exceptions.raise_compiler_error('A production close needs close_request_id') }}
{% else %}
where delivery_id = '{{ var("historical_price_delivery_id") }}'
   or delivery_id in (
       select delivery_id
       from {{ source('operations', 'deliveries') }}
       where source_name = 'daily_prices'
         and delivery_status = 'READY'
         and expected_rows = received_rows
   )
{% endif %}
