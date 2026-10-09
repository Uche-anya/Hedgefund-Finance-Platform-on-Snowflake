select valuation_date, market_ticker, count(*) as row_count
from {{ ref('stg_prices') }}
group by 1, 2
having count(*) > 1
