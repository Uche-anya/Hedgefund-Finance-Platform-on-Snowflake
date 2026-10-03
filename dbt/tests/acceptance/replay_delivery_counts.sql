{{ config(tags=['fixture']) }}
with expected as (
    select
        column1 as record_type,
        column2 as records
    from values ('EXECUTION', 3200), ('SETTLEMENT', 3168), ('SESSION', 23), ('OPENING_CASH', 2), ('DIVIDEND_PAYMENT', 1)
),

received as (
    select
        record_type,
        count(*) as records
    from {{ ref('stg_activity_events') }}
    group by record_type
)
select
    e.record_type,
    r.records
from expected e full outer join received r on e.record_type = r.record_type
where e.record_type is null
   or r.record_type is null
   or e.records <> r.records
