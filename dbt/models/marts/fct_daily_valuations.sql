with prices as (
    select p.*, i.security_id
    from {{ ref('stg_historical_prices') }} p
    join {{ ref('dim_instrument') }} i
      on p.universe_ticker = i.ticker
     and p.valuation_date between i.valid_from and i.valid_to
)
select
    h.*,
    p.close_price,
    h.closing_quantity * p.close_price as market_value,
    p.delivery_id as price_delivery_id,
    p.identity_status as price_identity_status
from {{ ref('fct_daily_positions') }} h
left join prices p
    on h.security_id = p.security_id and h.market_ticker = p.source_ticker
    and h.business_date = p.valuation_date and h.currency = p.currency
    and p.price_basis = 'unadjusted'
