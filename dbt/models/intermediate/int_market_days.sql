-- Dates for which the selected price delivery has a full market session.
select distinct valuation_date as business_date
from {{ ref('stg_historical_prices') }}
where universe_ticker = 'AAPL'
