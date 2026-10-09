select
    try_to_date(r.payload:settlement_date::varchar) as settlement_date,
    r.payload:scenario_id::varchar as scenario_id,
    r.payload:account_id::varchar as account_id,
    r.payload:execution_id::varchar as execution_id,
    r.payload:settlement_id::varchar as settlement_id,
    r.payload:side::varchar as side,
    try_to_decimal(r.payload:settled_quantity::varchar, 38, 9) as settled_quantity,
    try_to_decimal(r.payload:cash_amount::varchar, 38, 9) as cash_amount,
    r.payload:currency::varchar as currency,
    r.source_file
from {{ source('raw', 'daily_settlement_events') }} r
join {{ source('raw', 'daily_deliveries') }} d
    on d.source_name = 'settlements'
    and d.scenario_id = '{{ var("scenario_id") }}'
    and d.status = 'SUBMITTED'
    and d.business_date <= to_date('{{ var("business_date") }}')
    and endswith(r.source_file, d.stage_path)
where r.payload:settlement_status::varchar = 'SETTLED'
