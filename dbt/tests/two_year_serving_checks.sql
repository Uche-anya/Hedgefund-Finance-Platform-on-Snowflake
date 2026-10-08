{{ config(tags=['fixture']) }}

-- A row is returned for any broken grain, failed cast, or source row loss.
with account_rows as (
    select scenario_id, ledger_id, business_date, account_id, count(*) as n
    from {{ ref('cmp_python_account_day') }}
    group by 1, 2, 3, 4
), position_rows as (
    select scenario_id, ledger_id, business_date, account_id, security_id, count(*) as n
    from {{ ref('cmp_python_position_day') }}
    group by 1, 2, 3, 4, 5
), counts as (
    select record_type, count(*) as n
    from {{ source('raw', 'two_year_reporting') }}
    where ledger_id = '{{ var("comparison_ledger_id") }}'
    group by 1
)
select 'account grain or cast' as issue from account_rows
where n <> 1 or scenario_id is null or business_date is null or account_id is null
union all
select 'position grain or cast' from position_rows
where n <> 1 or scenario_id is null or business_date is null
   or account_id is null or security_id is null
union all
select 'account value cast' from {{ ref('cmp_python_account_day') }}
where reviewed_nav_usd is null or net_market_value_usd is null
   or gross_market_exposure_usd is null or pending_candidate_impact_usd is null
union all
select 'position value cast' from {{ ref('cmp_python_position_day') }}
where quantity is null or close_price_usd is null or market_value_usd is null
union all
select 'account source count' where
    (select count(*) from {{ ref('cmp_python_account_day') }}) <>
    coalesce((select n from counts where record_type = 'account_day'), -1)
union all
select 'position source count' where
    (select count(*) from {{ ref('cmp_python_position_day') }}) <>
    coalesce((select n from counts where record_type = 'position_day'), -1)
