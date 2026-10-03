select
    payload:record_id::varchar as record_id,
    payload:statement_id::varchar as statement_id,
    payload:scenario_id::varchar as scenario_id,
    try_to_date(payload:statement_date::varchar, 'YYYY-MM-DD') as statement_date,
    payload:account_id::varchar as account_id,
    payload:currency::varchar as currency,
    try_to_decimal(payload:closing_balance::varchar, 38, 9) as closing_balance,
    try_to_timestamp_tz(payload:published_at::varchar) as published_at,
    payload:source_system::varchar as source_system,
    payload:is_simulated::boolean as is_simulated,
    delivery_id,
    loaded_at
from {{ source('raw', 'bank_cash_statements') }}
where delivery_id = '{{ var("bank_delivery_id") }}'
