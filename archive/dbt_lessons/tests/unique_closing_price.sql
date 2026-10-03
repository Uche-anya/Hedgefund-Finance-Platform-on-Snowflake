-- Our current contract allows one USD unadjusted price per stock per day.
select
    valuation_date,
    instrument,
    count(*) as price_count
from {{ ref('stg_closing_prices') }}
group by valuation_date, instrument
having count(*) > 1
