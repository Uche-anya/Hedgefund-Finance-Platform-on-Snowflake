{{ config(materialized='view') }}

with deliveries as (
    select business_date, scenario_id, delivery_id, stage_path
    from {{ source('raw', 'daily_deliveries') }}
    where source_name = 'bank' and status = 'LOADED'
), bank_rows as (
    select r.payload, r.source_file, r.source_row_number, d.delivery_id
    from {{ source('raw', 'daily_bank_statements') }} r
    join deliveries d on endswith(r.source_file, d.stage_path)
), postings as (
    select b.source_file, b.source_row_number,
        coalesce(sum(try_to_decimal(p.value:amount::varchar, 38, 2)), 0) as posted_cash,
        count_if(p.value is not null
            and try_to_decimal(p.value:amount::varchar, 38, 2) is null) as bad_postings
    from bank_rows b, lateral flatten(input => b.payload:postings, outer => true) p
    group by 1, 2
), bank as (
    select
        try_to_date(b.payload:statement_date::varchar) as statement_date,
        try_to_date(b.payload:previous_statement_date::varchar) as previous_statement_date,
        b.payload:scenario_id::varchar as scenario_id,
        b.payload:account_id::varchar as account_id,
        b.payload:currency::varchar as currency,
        try_to_decimal(b.payload:closing_balance::varchar, 38, 2) as bank_cash,
        try_to_decimal(b.payload:opening_balance::varchar, 38, 2) as bank_opening_cash,
        b.payload:postings is not null as has_postings,
        p.posted_cash, p.bad_postings, b.delivery_id,
        count(*) over (partition by b.payload:statement_date::varchar,
            b.payload:scenario_id::varchar, b.payload:account_id::varchar) as account_rows
    from bank_rows b
    join postings p
        on p.source_file = b.source_file
        and p.source_row_number = b.source_row_number
), cash as (
    select c.*, d.delivery_id
    from {{ ref('fct_cash_daily') }} c
    join deliveries d
        on d.business_date = c.valuation_date
        and d.scenario_id = c.scenario_id
), prior_bank as (
    select statement_date, scenario_id, account_id, bank_cash
    from bank
)
select
    coalesce(b.statement_date, c.valuation_date) as statement_date,
    coalesce(b.scenario_id, c.scenario_id) as scenario_id,
    coalesce(b.account_id, c.account_id) as account_id,
    b.currency,
    b.bank_cash,
    b.bank_opening_cash,
    b.posted_cash,
    c.calculated_cash_balance,
    b.bank_cash - c.calculated_cash_balance as difference_usd,
    case
        when b.account_id is null then 'MISSING_BANK_STATEMENT'
        when c.account_id is null then 'MISSING_MODEL_CASH'
        when b.account_rows != 1 then 'DUPLICATE_BANK_ROW'
        when b.currency != 'USD' or b.bank_cash is null then 'BAD_BANK_BALANCE'
        when b.statement_date >= to_date('2026-10-19') and not b.has_postings
            then 'MISSING_BANK_LEDGER'
        when b.has_postings and (b.previous_statement_date is null
            or b.previous_statement_date >= b.statement_date
            or b.bank_opening_cash is null or b.bad_postings > 0
            or b.bank_opening_cash + b.posted_cash != b.bank_cash)
            then 'BAD_BANK_ROLLFORWARD'
        when b.has_postings
            and b.previous_statement_date = to_date('{{ var("opening_date") }}')
            and (o.opening_cash is null or b.bank_opening_cash != o.opening_cash)
            then 'BAD_BANK_OPENING'
        when b.has_postings
            and b.previous_statement_date != to_date('{{ var("opening_date") }}')
            and p.bank_cash is null then 'MISSING_PRIOR_BANK'
        when b.has_postings
            and b.previous_statement_date != to_date('{{ var("opening_date") }}')
            and b.bank_opening_cash != p.bank_cash then 'BAD_BANK_OPENING'
        when b.bank_cash = c.calculated_cash_balance then 'MATCH'
        else 'BREAK'
    end as reconciliation_status,
    coalesce(b.delivery_id, c.delivery_id) as delivery_id
from bank b
full outer join cash c
    on c.valuation_date = b.statement_date
    and c.scenario_id = b.scenario_id
    and c.account_id = b.account_id
left join prior_bank p
    on p.statement_date = b.previous_statement_date
    and p.scenario_id = b.scenario_id
    and p.account_id = b.account_id
left join {{ ref('stg_opening_cash') }} o
    on o.scenario_id = b.scenario_id
    and o.account_id = b.account_id
