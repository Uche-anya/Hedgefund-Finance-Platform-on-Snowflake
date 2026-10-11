-- A retry may repeat a report; a changed trade needs a new execution version.
with reports as (
    select
        r.payload:scenario_id::varchar as scenario_id,
        r.payload:execution_id::varchar as execution_id,
        try_to_number(r.payload:execution_version::varchar) as execution_version,
        hash(
            r.payload:business_date::varchar,
            r.payload:executed_at::varchar,
            r.payload:order_id::varchar,
            r.payload:fund_id::varchar,
            r.payload:account_id::varchar,
            r.payload:broker_id::varchar,
            r.payload:instrument_id::varchar,
            r.payload:market_ticker::varchar,
            r.payload:side::varchar,
            r.payload:quantity::varchar,
            r.payload:execution_price::varchar,
            r.payload:currency::varchar,
            r.payload:execution_status::varchar,
            r.payload:settlement_due::varchar
        ) as trade_details
    from {{ source('raw', 'daily_oms_events') }} r
    join {{ source('raw', 'daily_deliveries') }} d
        on d.source_name = 'oms'
        and d.scenario_id = '{{ var("scenario_id") }}'
        and d.status = 'SUBMITTED'
        and d.business_date <= to_date('{{ var("business_date") }}')
        and endswith(r.source_file, d.stage_path)
    where r.payload:event_type::varchar = 'EXECUTION_REPORTED'
)
select scenario_id, execution_id, execution_version
from reports
group by 1, 2, 3
having count(distinct trade_details) > 1
