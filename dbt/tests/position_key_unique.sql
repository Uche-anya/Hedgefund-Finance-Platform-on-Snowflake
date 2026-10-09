select valuation_date, scenario_id, account_id, instrument_id, count(*) as row_count
from {{ ref('fct_position_daily') }}
group by 1, 2, 3, 4
having count(*) > 1
