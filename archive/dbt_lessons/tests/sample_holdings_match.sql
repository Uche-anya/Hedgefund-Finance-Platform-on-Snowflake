-- Independently worked expected answer for this particular learning delivery.
{% if var('delivery_id') == '18ae80085f1043789b5d604ee44dc216' %}
with expected as (
    select
        column1 as portfolio,
        column2 as instrument,
        column3 as quantity
    from values ('GROWTH', 'AAPL.US', 10), ('HEDGE', 'AMZN.US', -5)
)
select
    h.*,
    e.quantity as expected_quantity
from {{ ref('portfolio_holdings') }} h
full outer join expected e
    on h.portfolio = e.portfolio and h.instrument = e.instrument
where h.portfolio is null
   or e.portfolio is null

      or h.quantity is null
      or h.quantity <> e.quantity
{% else %}
select *
from {{ ref('portfolio_holdings') }}
where false
{% endif %}
