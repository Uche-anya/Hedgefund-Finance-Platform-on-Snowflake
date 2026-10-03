-- Independently calculated values for our saved January 6 example.
{% if var('delivery_id') == '18ae80085f1043789b5d604ee44dc216'
  and var('price_delivery_id') == '0a35a13d137e4627ace8d7a9d668f3ce'
  and var('business_date') == '2025-01-06' %}
with expected as (
    select
        to_date('2025-01-06', 'YYYY-MM-DD') as valuation_date,
        column1 as portfolio, column2 as instrument, column3 as market_value
    from values ('GROWTH', 'AAPL.US', 2450.00), ('HEDGE', 'AMZN.US', -1138.05)
)
select
    v.*,
    e.market_value as expected_value
from {{ ref('portfolio_valuation') }} v
full outer join expected e
    on v.valuation_date = e.valuation_date
    and v.portfolio = e.portfolio
    and v.instrument = e.instrument
where v.instrument is null
   or e.instrument is null

      or v.market_value is null
      or v.market_value <> e.market_value
{% else %}
select *
from {{ ref('portfolio_valuation') }}
where false
{% endif %}
