-- The bank opening is the starting cash; the fund-admin subscription is a check.
with bank as (
    select r.payload, r.source_file
    from {{ source('raw', 'daily_opening_events') }} r
    join {{ source('raw', 'daily_deliveries') }} d
        on d.source_name = 'opening_bank'
        and d.scenario_id = '{{ var("scenario_id") }}'
        and d.business_date = to_date('{{ var("opening_date") }}')
        and d.status = 'LOADED'
        and endswith(r.source_file, d.stage_path)
), admin as (
    select r.payload, r.source_file
    from {{ source('raw', 'daily_opening_events') }} r
    join {{ source('raw', 'daily_deliveries') }} d
        on d.source_name = 'opening_admin'
        and d.scenario_id = '{{ var("scenario_id") }}'
        and d.business_date = to_date('{{ var("opening_date") }}')
        and d.status = 'LOADED'
        and endswith(r.source_file, d.stage_path)
)
select
    coalesce(try_to_date(b.payload:statement_date::varchar),
             try_to_date(a.payload:event_date::varchar)) as opening_date,
    coalesce(b.payload:scenario_id::varchar, a.payload:scenario_id::varchar) as scenario_id,
    coalesce(b.payload:account_id::varchar, a.payload:account_id::varchar) as account_id,
    coalesce(b.payload:currency::varchar, a.payload:currency::varchar) as currency,
    try_to_decimal(b.payload:closing_balance::varchar, 38, 9) as opening_cash,
    try_to_decimal(a.payload:amount::varchar, 38, 9) as subscription_amount,
    b.source_file as bank_file,
    a.source_file as admin_file
from bank b
full outer join admin a
    on a.payload:scenario_id::varchar = b.payload:scenario_id::varchar
    and a.payload:account_id::varchar = b.payload:account_id::varchar
    and a.payload:currency::varchar = b.payload:currency::varchar
