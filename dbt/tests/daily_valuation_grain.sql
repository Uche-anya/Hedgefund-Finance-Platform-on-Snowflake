select
    scenario_id,
    account_id,
    instrument_id,
    business_date,
    count(*) as rows_valued
from {{ ref('fct_daily_valuations') }}
group by scenario_id, account_id, instrument_id, business_date
having count(*) <> 1
   or count(market_value) <> count(*)
