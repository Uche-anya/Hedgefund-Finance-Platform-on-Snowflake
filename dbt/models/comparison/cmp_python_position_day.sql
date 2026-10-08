{{ config(tags=['fixture']) }}

-- One account, security and market date from the saved Python comparison close.
select
    payload:scenario_id::varchar as scenario_id,
    ledger_id,
    'EXPLORATORY_PROVISIONAL' as reporting_status,
    try_to_date(payload:business_date::varchar, 'YYYY-MM-DD') as business_date,
    payload:account_id::varchar as account_id,
    payload:security_id::varchar as security_id,
    payload:instrument_version_id::varchar as instrument_version_id,
    payload:ticker_as_of_date::varchar as ticker_as_of_date,
    payload:security_name_as_of_date::varchar as security_name_as_of_date,
    payload:position_side::varchar as position_side,
    try_to_decimal(payload:quantity::varchar, 38, 9) as quantity,
    try_to_decimal(payload:close_price_usd::varchar, 38, 9) as close_price_usd,
    try_to_decimal(payload:market_value_usd::varchar, 38, 9) as market_value_usd,
    try_to_decimal(payload:signed_weight_to_reviewed_nav_ratio::varchar, 38, 12) as signed_weight_to_reviewed_nav_ratio,
    try_to_decimal(payload:absolute_weight_of_gross_exposure_ratio::varchar, 38, 12) as absolute_weight_of_gross_exposure_ratio,
    manifest_sha256
from {{ source('raw', 'two_year_reporting') }}
where ledger_id = '{{ var("comparison_ledger_id") }}'
  and record_type = 'position_day'
