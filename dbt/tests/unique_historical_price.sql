select
    delivery_id,
    universe_ticker,
    valuation_date,
    count(*) as records
from {{ ref('stg_historical_prices') }}
group by delivery_id, universe_ticker, valuation_date
having count(*) > 1
