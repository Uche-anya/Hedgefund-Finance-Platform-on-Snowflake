select
    universe_ticker,
    valuation_date,
    count(*) as records
from {{ ref('stg_historical_prices') }}
group by universe_ticker, valuation_date
having count(*) > 1
