-- Use only files registered for this scenario. Keep the latest report for each execution.
with received as (
    select
        r.payload,
        r.source_file,
        r.source_row_number
    from {{ source('raw', 'daily_oms_events') }} r
    join {{ source('raw', 'daily_deliveries') }} d
        on d.source_name = 'oms'
        and d.scenario_id = '{{ var("scenario_id") }}'
        and d.status = 'SUBMITTED'
        and d.business_date <= to_date('{{ var("business_date") }}')
        and endswith(r.source_file, d.stage_path)
), typed as (
    select
        try_to_date(payload:business_date::varchar) as business_date,
        payload:scenario_id::varchar as scenario_id,
        payload:account_id::varchar as account_id,
        payload:execution_id::varchar as execution_id,
        payload:instrument_id::varchar as instrument_id,
        payload:market_ticker::varchar as market_ticker,
        payload:side::varchar as side,
        try_to_decimal(payload:quantity::varchar, 38, 9) as quantity,
        try_to_decimal(payload:execution_price::varchar, 38, 9) as execution_price,
        payload:currency::varchar as currency,
        try_to_number(payload:execution_version::varchar) as execution_version,
        payload:execution_status::varchar as execution_status,
        try_to_timestamp_tz(payload:published_at::varchar) as published_at,
        source_file,
        source_row_number
    from received
    where payload:event_type::varchar = 'EXECUTION_REPORTED'
)
select *
from typed
qualify row_number() over (
    partition by scenario_id, execution_id
    order by execution_version desc, published_at desc, source_file desc, source_row_number desc
) = 1
