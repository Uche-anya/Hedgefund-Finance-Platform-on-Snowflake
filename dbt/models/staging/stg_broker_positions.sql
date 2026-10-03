with received as (
    select
        payload:record_id::varchar as record_id,
        payload:statement_id::varchar as statement_id,
        payload:statement_date::varchar as statement_date_raw,
        payload:position_basis::varchar as position_basis,
        payload:fund_id::varchar as fund_id,
        payload:broker_id::varchar as broker_id,
        payload:account_id::varchar as account_id,
        payload:broker_instrument_id::varchar as broker_instrument_id,
        payload:ticker::varchar as reported_ticker,
        payload:currency::varchar as currency,
        payload:quantity::varchar as quantity_raw,
        payload:published_at::varchar as published_at_raw,
        payload:source_system::varchar as source_system,
        payload:is_simulated::boolean as is_simulated,
        delivery_id,
        source_file,
        source_row_number,
        loaded_at
    from {{ source('raw', 'broker_positions') }}
    where delivery_id = '{{ var("broker_delivery_id") }}'
),

typed as (
    select
        *,
        try_to_date(statement_date_raw, 'YYYY-MM-DD') as statement_date,
        try_to_timestamp_tz(published_at_raw) as published_at,
        case when regexp_like(quantity_raw, '^-?[0-9]{1,29}([.][0-9]{1,9})?$')
            then try_to_decimal(quantity_raw, 38, 9) end as quantity
    from received
)
select
    t.*,
    i.security_id,
    i.ticker as mastered_ticker
from typed t
left join {{ ref('dim_instrument') }} i
  on t.broker_instrument_id = i.share_class_figi
 and t.statement_date between i.valid_from and i.valid_to
