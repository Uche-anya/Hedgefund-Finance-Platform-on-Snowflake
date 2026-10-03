-- A changed ticker label must not split one instrument into two positions.
select
    scenario_id,
    business_date,
    fund_id,
    account_id,
    instrument_id,
    count(*) as position_rows
from {{ ref('oms_first_day_positions') }}
group by scenario_id, business_date, fund_id, account_id, instrument_id
having count(*) > 1
