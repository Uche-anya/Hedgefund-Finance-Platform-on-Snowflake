-- Keep every received message. Duplicate event IDs should fail a test.
with received as (
    select
        payload:event_id::varchar as event_id,
        payload:execution_id::varchar as execution_id,
        payload:order_id::varchar as order_id,
        payload:event_type::varchar as event_type,
        payload:execution_status::varchar as execution_status,
        payload:execution_version::varchar as execution_version,
        payload:schema_version::varchar as schema_version,
        payload:is_simulated::varchar as is_simulated,
        payload:fund_id::varchar as fund_id,
        payload:account_id::varchar as account_id,
        payload:broker_id::varchar as broker_id,
        payload:instrument_id::varchar as instrument_id,
        payload:market_ticker::varchar as market_ticker,
        payload:side::varchar as side,
        payload:currency::varchar as currency,
        payload:business_date::varchar as business_date_raw,
        payload:settlement_due::varchar as settlement_due_raw,
        payload:executed_at::varchar as executed_at_raw,
        payload:published_at::varchar as published_at_raw,
        payload:quantity::varchar as quantity_raw,
        payload:execution_price::varchar as execution_price_raw,
        payload:source_system::varchar as message_source_system,
        payload:scenario_id::varchar as message_scenario_id,
        source_system,
        scenario_id,
        delivery_id,
        source_file,
        source_row_number,
        loaded_at
    from {{ source('raw', 'oms_events') }}
    where delivery_id = '{{ var("oms_delivery_id") }}'
)
select
    received.*,
    try_to_date(business_date_raw, 'YYYY-MM-DD') as business_date,
    try_to_date(settlement_due_raw, 'YYYY-MM-DD') as settlement_due,
    try_to_timestamp_tz(executed_at_raw) as executed_at,
    try_to_timestamp_tz(published_at_raw) as published_at,
    -- Reject excess decimal places rather than rounding the received value.
    case when regexp_like(quantity_raw, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(quantity_raw, 38, 9)
    end as quantity,
    case when regexp_like(execution_price_raw, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(execution_price_raw, 38, 9)
    end as execution_price
from received
