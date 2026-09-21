-- Keep all dates in this price delivery. Valuation will choose the holdings date.
-- Remove exact repeats; conflicting prices remain so the duplicate test fails.
with received as (
    select distinct
        valuation_date as valuation_date_raw,
        instrument,
        currency,
        close_price as close_price_raw,
        price_basis,
        source_system,
        delivery_id
    from {{ source('raw', 'closing_prices') }}
    where source_system = 'eodhd_demo'
      and delivery_id = '{{ var("price_delivery_id") }}'
)
select
    valuation_date_raw,
    try_to_date(valuation_date_raw, 'YYYY-MM-DD') as valuation_date,
    instrument,
    currency,
    close_price_raw,
    -- Reject extra precision instead of rounding the received price.
    case when regexp_like(close_price_raw, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(close_price_raw, 38, 9)
    end as close_price,
    price_basis,
    source_system,
    delivery_id
from received
