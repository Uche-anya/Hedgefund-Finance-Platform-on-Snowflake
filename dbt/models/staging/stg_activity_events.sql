with received as (
    select
        payload:record_type::varchar as record_type,
        payload:scenario_id::varchar as scenario_id,
        payload:source_system::varchar as source_system,
        payload:is_simulated::varchar as is_simulated,
        payload:event_id::varchar as event_id,
        payload:execution_id::varchar as execution_id,
        payload:corporate_action_id::varchar as corporate_action_id,
        payload:account_id::varchar as account_id,
        payload:instrument_id::varchar as instrument_id,
        payload:market_ticker::varchar as market_ticker,
        payload:currency::varchar as currency,
        payload:side::varchar as side,
        payload:business_date::varchar as business_date_raw,
        payload:settlement_due::varchar as settlement_due_raw,
        payload:published_at::varchar as published_at_raw,
        payload:settled_at::varchar as settled_at_raw,
        payload:cutoff::varchar as cutoff_raw,
        payload:reference_price_date::varchar as reference_date_raw,
        case when payload:record_type::varchar = 'SETTLEMENT'
             then payload:settled_quantity::varchar else payload:quantity::varchar end as quantity_raw,
        payload:execution_price::varchar as execution_price_raw,
        payload:cash_amount::varchar as cash_amount_raw,
        payload:amount::varchar as opening_cash_raw,
        delivery_id, source_file, source_row_number, loaded_at
    from {{ source('raw', 'replay_inputs') }}
    where delivery_id = '{{ var("replay_delivery_id") }}'
)
select
    received.*,
    try_to_date(business_date_raw, 'YYYY-MM-DD') as business_date,
    try_to_date(settlement_due_raw, 'YYYY-MM-DD') as settlement_due,
    try_to_date(reference_date_raw, 'YYYY-MM-DD') as reference_date,
    try_to_timestamp_tz(published_at_raw) as published_at,
    try_to_timestamp_tz(settled_at_raw) as settled_at,
    try_to_timestamp_tz(cutoff_raw) as cutoff,
    case when regexp_like(quantity_raw, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(quantity_raw, 38, 9) end as quantity,
    case when regexp_like(execution_price_raw, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(execution_price_raw, 38, 9) end as execution_price,
    case when regexp_like(cash_amount_raw, '^-?[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(cash_amount_raw, 38, 9) end as cash_amount,
    case when regexp_like(opening_cash_raw, '^[0-9]{1,29}([.][0-9]{1,9})?$')
        then try_to_decimal(opening_cash_raw, 38, 9) end as opening_cash
from received
