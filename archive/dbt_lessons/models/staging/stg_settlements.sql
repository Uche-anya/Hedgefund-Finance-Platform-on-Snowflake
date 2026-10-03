with received as (
    select
        payload:event_id::varchar as event_id,
        payload:settlement_id::varchar as settlement_id,
        payload:execution_id::varchar as execution_id,
        payload:scenario_id::varchar as scenario_id,
        payload:fund_id::varchar as fund_id,
        payload:account_id::varchar as account_id,
        payload:broker_id::varchar as broker_id,
        payload:instrument_id::varchar as instrument_id,
        payload:side::varchar as side,
        payload:currency::varchar as currency,
        payload:source_system::varchar as source_system,
        payload:event_type::varchar as event_type,
        payload:settlement_status::varchar as settlement_status,
        payload:is_simulated::varchar as is_simulated,
        payload:schema_version::varchar as schema_version,
        payload:cash_amount::varchar as cash_amount_raw,
        payload:settled_quantity::varchar as settled_quantity_raw,
        payload:settlement_date::varchar as settlement_date_raw,
        payload:settled_at::varchar as settled_at_raw,
        payload:published_at::varchar as published_at_raw,
        delivery_id, source_file, source_row_number, loaded_at
    from {{ source('raw', 'settlement_events') }}
    where delivery_id = '{{ var("settlement_delivery_id") }}'

          or delivery_id = '{{ var("settlement_late_delivery_id", "") }}'
)
select
    received.*,
    case when regexp_like(cash_amount_raw, '^-?[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(cash_amount_raw, 38, 9) end as cash_amount,
    case when regexp_like(settled_quantity_raw, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(settled_quantity_raw, 38, 9) end as settled_quantity,
    try_to_date(settlement_date_raw, 'YYYY-MM-DD') as settlement_date,
    try_to_timestamp_tz(settled_at_raw) as settled_at,
    try_to_timestamp_tz(published_at_raw) as published_at
from received
