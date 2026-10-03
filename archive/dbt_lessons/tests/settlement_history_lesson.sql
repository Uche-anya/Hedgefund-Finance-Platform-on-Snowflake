-- Both views of the past must survive the late-message replay.
with expected as (
    select
        '2025-01-07T22:00:00+00:00'::timestamp_tz as cutoff,
        4 as matches,
        1 as missing

    union all

    select
        '2025-01-08T10:00:00+00:00'::timestamp_tz,
        5,
        0
    where '{{ var("settlement_cutoff") }}'::timestamp_tz
        >= '2025-01-08T10:00:00+00:00'::timestamp_tz
)
select
    e.cutoff,
    count(h.execution_id) as saved_rows
from expected e
left join {{ ref('settlement_report_history') }} h
    on h.as_of = e.cutoff
    and h.scenario_id = 'sim-historical-f9b72e1aa20041068cea4d5ac0b2eaf8'
group by e.cutoff
having count(h.execution_id) <> 5

       or coalesce(count_if(h.reconciliation_status = 'MATCHED'), 0) <> max(e.matches)

       or coalesce(count_if(h.reconciliation_status = 'NO_CONFIRMATION'), 0) <> max(e.missing)
