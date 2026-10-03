-- The fixed AAPL/AMZN lesson uses provider tickers, not permanent security IDs.
select
    h.scenario_id,
    h.business_date as valuation_date,
    h.fund_id,
    h.account_id,
    h.instrument_id,
    h.market_ticker,
    h.currency,
    h.closing_quantity,
    p.close_price,
    h.closing_quantity * p.close_price as market_value,
    p.price_basis,
    p.identity_status as price_identity_status,
    p.source_ticker as price_source_ticker,
    p.source_system as price_source,
    p.delivery_id as price_delivery_id,
    p.source_file as price_source_file,
    p.source_row_number as price_source_row_number,
    '{{ var("oms_delivery_id") }}' as oms_delivery_id
from {{ ref('oms_first_day_positions') }} h
left join {{ ref('stg_historical_prices') }} p
    on h.market_ticker = p.universe_ticker
    and h.market_ticker = p.source_ticker
    and h.business_date = p.valuation_date
    and h.currency = p.currency
    and p.price_basis = 'unadjusted'
