select
    payload:record_id::varchar as record_id,
    payload:scenario_id::varchar as scenario_id,
    payload:event_type::varchar as event_type,
    try_to_date(payload:event_date::varchar, 'YYYY-MM-DD') as event_date,
    try_to_date(payload:payment_date::varchar, 'YYYY-MM-DD') as payment_date,
    payload:account_id::varchar as account_id,
    payload:currency::varchar as currency,
    try_to_decimal(payload:amount::varchar, 38, 9) as amount,
    payload:expense_type::varchar as expense_type,
    payload:source_system::varchar as source_system,
    payload:is_simulated::boolean as is_simulated,
    delivery_id,
    loaded_at
from {{ source('raw', 'fund_admin_events') }}
where delivery_id = '{{ var("fund_admin_delivery_id") }}'
