{{ config(materialized='view') }}

with deliveries as (
    select business_date, scenario_id, delivery_id, stage_path
    from {{ source('raw', 'daily_deliveries') }}
    where source_name = 'bank' and status = 'LOADED'
), bank as (
    select
        try_to_date(r.payload:statement_date::varchar) as statement_date,
        r.payload:scenario_id::varchar as scenario_id,
        r.payload:account_id::varchar as account_id,
        r.payload:currency::varchar as currency,
        try_to_decimal(r.payload:closing_balance::varchar, 38, 2) as bank_cash,
        d.delivery_id,
        count(*) over (partition by d.business_date, d.scenario_id,
            r.payload:account_id::varchar) as account_rows
    from {{ source('raw', 'daily_bank_statements') }} r
    join deliveries d on endswith(r.source_file, d.stage_path)
), cash as (
    select c.*, d.delivery_id
    from {{ ref('fct_cash_daily') }} c
    join deliveries d
        on d.business_date = c.valuation_date
        and d.scenario_id = c.scenario_id
)
select
    coalesce(b.statement_date, c.valuation_date) as statement_date,
    coalesce(b.scenario_id, c.scenario_id) as scenario_id,
    coalesce(b.account_id, c.account_id) as account_id,
    b.currency,
    b.bank_cash,
    c.calculated_cash_balance,
    b.bank_cash - c.calculated_cash_balance as difference_usd,
    case
        when b.account_id is null then 'MISSING_BANK_STATEMENT'
        when c.account_id is null then 'MISSING_MODEL_CASH'
        when b.account_rows != 1 then 'DUPLICATE_BANK_ROW'
        when b.currency != 'USD' or b.bank_cash is null then 'BAD_BANK_BALANCE'
        when b.bank_cash = c.calculated_cash_balance then 'MATCH'
        else 'BREAK'
    end as reconciliation_status,
    coalesce(b.delivery_id, c.delivery_id) as delivery_id
from bank b
full outer join cash c
    on c.valuation_date = b.statement_date
    and c.scenario_id = b.scenario_id
    and c.account_id = b.account_id
