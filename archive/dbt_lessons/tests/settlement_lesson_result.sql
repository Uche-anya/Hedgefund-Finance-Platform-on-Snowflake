-- Fixed lesson expectation; the reconciliation itself never reads this list.
with expected as (
    select
        execution_id,
        case when execution_id = 'SIM-EXEC-bf8211379ba04580a5b707ada1183f9d'
                  and not (
                      '{{ var("settlement_late_delivery_id", "") }}' <> ''
                      and '{{ var("settlement_cutoff") }}'::timestamp_tz
                          >= '2025-01-08T09:00:00+00:00'::timestamp_tz
                  )
             then 'NO_CONFIRMATION' else 'MATCHED' end as status
    from {{ ref('oms_trade_cash') }}
)
select
    e.execution_id as expected_execution,
    r.*
from expected e
full outer join {{ ref('oms_settlement_reconciliation') }} r
    on e.execution_id = r.execution_id
where e.execution_id is null
   or r.execution_id is null

      or e.status <> r.reconciliation_status

      or (e.status = 'MATCHED' and (r.cash_difference is null
      or r.cash_difference <> 0))

      or (e.status = 'NO_CONFIRMATION' and r.confirmed_cash_change is not null)
