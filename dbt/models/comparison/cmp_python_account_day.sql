{{ config(tags=['fixture']) }}

-- One account on one market date from the saved Python comparison close.
-- The close is calculated in Python; this table is its Snowflake serving copy.
select
    payload:scenario_id::varchar as scenario_id,
    ledger_id,
    'EXPLORATORY_PROVISIONAL' as reporting_status,
    try_to_date(payload:business_date::varchar, 'YYYY-MM-DD') as business_date,
    payload:account_id::varchar as account_id,
    payload:currency::varchar as currency,
    payload:nav_status::varchar as nav_status,
    try_to_decimal(payload:reviewed_nav_usd::varchar, 38, 9) as reviewed_nav_usd,
    try_to_decimal(payload:illustrative_nav_usd::varchar, 38, 9) as illustrative_nav_usd,
    try_to_decimal(payload:pending_candidate_impact_usd::varchar, 38, 9) as pending_candidate_impact_usd,
    try_to_decimal(payload:settled_cash_usd::varchar, 38, 9) as settled_cash_usd,
    try_to_decimal(payload:trade_receivable_usd::varchar, 38, 9) as trade_receivable_usd,
    try_to_decimal(payload:trade_payable_usd::varchar, 38, 9) as trade_payable_usd,
    try_to_decimal(payload:reviewed_dividend_receivable_usd::varchar, 38, 9) as reviewed_dividend_receivable_usd,
    try_to_decimal(payload:reviewed_short_dividend_payable_usd::varchar, 38, 9) as reviewed_short_dividend_payable_usd,
    try_to_decimal(payload:long_market_value_usd::varchar, 38, 9) as long_market_value_usd,
    try_to_decimal(payload:short_market_value_abs_usd::varchar, 38, 9) as short_market_value_abs_usd,
    try_to_decimal(payload:net_market_value_usd::varchar, 38, 9) as net_market_value_usd,
    try_to_decimal(payload:gross_market_exposure_usd::varchar, 38, 9) as gross_market_exposure_usd,
    try_to_decimal(payload:gross_exposure_to_reviewed_nav_ratio::varchar, 38, 12) as gross_exposure_to_reviewed_nav_ratio,
    try_to_decimal(payload:net_exposure_to_reviewed_nav_ratio::varchar, 38, 12) as net_exposure_to_reviewed_nav_ratio,
    manifest_sha256
from {{ source('raw', 'two_year_reporting') }}
where ledger_id = '{{ var("comparison_ledger_id") }}'
  and record_type = 'account_day'
