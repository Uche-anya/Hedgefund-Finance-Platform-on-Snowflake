-- Fixed-snapshot check, calculated independently from the saved CSV prices.
{% if var('historical_price_delivery_id') == 'fb25ddd9838840488e4c8b971ff7e0ae' %}
with expected as (
    select
        'AAPL.US' as instrument_id,
        245.00 as price,
        3675.00 as value

    union all

    select
        'AMZN.US',
        227.61,
        -682.83
)
select
    e.instrument_id as expected_instrument,
    v.*
from expected e
full outer join {{ ref('oms_first_day_valuation') }} v
    on e.instrument_id = v.instrument_id
where e.instrument_id is null

      or v.instrument_id is null

      or v.close_price <> e.price

      or v.market_value <> e.value
{% else %}
select 1
where false
{% endif %}
