-- The saved late message is unavailable until its January 8 publication time.
with expected as (
    select 'SIM-EXEC-bf8211379ba04580a5b707ada1183f9d' as execution_id
    where not (
        '{{ var("settlement_late_delivery_id", "") }}' <> ''
        and '{{ var("settlement_cutoff") }}'::timestamp_tz
            >= '2025-01-08T09:00:00+00:00'::timestamp_tz
    )
)
select
    e.execution_id as expected_execution,
    r.*
from expected e
full outer join {{ ref('settlement_exceptions') }} r
    on e.execution_id = r.execution_id
where e.execution_id is null
   or r.execution_id is null

      or r.instrument_id is distinct
   from 'AMZN.US'

      or r.side is distinct
   from 'BUY'

      or r.expected_quantity is distinct
   from 2

      or r.expected_currency is distinct
   from 'USD'

      or r.expected_cash_change is distinct
   from -448.52

      or r.confirmed_cash_change is not null

      or r.exception_type is distinct
   from 'NO_CONFIRMATION'
