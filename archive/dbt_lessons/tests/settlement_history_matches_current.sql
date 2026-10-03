-- The saved report at the current cutoff must agree with the live report.
with saved as (
    select *
    from {{ ref('settlement_report_history') }}
    where as_of = '{{ var("settlement_cutoff") }}'::timestamp_tz
)
select
    r.execution_id,
    s.reconciliation_status as saved_status
from {{ ref('oms_settlement_reconciliation') }} r
full outer join saved s
    on r.scenario_id = s.scenario_id and r.execution_id = s.execution_id
    and r.as_of = s.as_of
where r.execution_id is null
   or s.execution_id is null

      or r.reconciliation_status is distinct
   from s.reconciliation_status

      or r.expected_cash_change is distinct
   from s.expected_cash_change

      or r.confirmed_cash_change is distinct
   from s.confirmed_cash_change

      or r.confirmation_event_id is distinct
   from s.confirmation_event_id
