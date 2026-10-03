select
    scenario_id,
    as_of,
    execution_id,
    count(*) as rows_saved
from {{ ref('settlement_report_history') }}
group by scenario_id, as_of, execution_id
having count(*) > 1
