select
    h.business_date as valuation_date,
    h.portfolio,
    h.instrument,
    h.quantity,
    p.currency,
    p.close_price,
    h.quantity * p.close_price as market_value,
    p.price_basis,
    p.source_system as price_source,
    p.delivery_id as price_delivery_id,
    '{{ var("delivery_id") }}' as holdings_delivery_id
from {{ ref('portfolio_holdings') }} h
left join {{ ref('stg_closing_prices') }} p
    on h.instrument = p.instrument
    and h.business_date = p.valuation_date
    and p.currency = 'USD'
    and p.price_basis = 'unadjusted'
