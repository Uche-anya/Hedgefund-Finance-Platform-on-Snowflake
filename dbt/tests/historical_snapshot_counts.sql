-- This expectation belongs only to the reviewed September snapshot.
{% if var('historical_price_delivery_id') == 'fb25ddd9838840488e4c8b971ff7e0ae' %}
select count(*) as records, count(distinct universe_ticker) as tickers
from {{ ref('stg_historical_prices') }}
having count(*) <> 250036 or count(distinct universe_ticker) <> 503
    or min(valuation_date) <> '2024-09-23'::date
    or max(valuation_date) <> '2026-09-21'::date
{% else %}
select 1 where false
{% endif %}
