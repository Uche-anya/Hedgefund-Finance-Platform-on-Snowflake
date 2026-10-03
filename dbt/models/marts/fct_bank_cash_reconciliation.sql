with internal_cash as (
    select business_date as statement_date, scenario_id, account_id, currency,
           reported_settled_cash as internal_balance
    from {{ ref('fct_daily_cash') }}
    where business_date = '{{ var("bank_statement_date") }}'
),
bank_cash as (
    select statement_date, scenario_id, account_id, currency,
           closing_balance as bank_balance, statement_id, published_at, delivery_id
    from {{ ref('stg_bank_cash_statements') }}
)
select
    coalesce(i.statement_date, b.statement_date) as statement_date,
    coalesce(i.scenario_id, b.scenario_id) as scenario_id,
    coalesce(i.account_id, b.account_id) as account_id,
    coalesce(i.currency, b.currency) as currency,
    i.internal_balance,
    b.bank_balance,
    b.bank_balance - i.internal_balance as balance_difference,
    case
        when i.account_id is null then 'UNEXPECTED_BANK_ACCOUNT'
        when b.account_id is null then 'MISSING_BANK_ACCOUNT'
        when i.internal_balance <> b.bank_balance then 'BALANCE_MISMATCH'
        else 'MATCHED'
    end as reconciliation_status,
    b.statement_id,
    b.published_at,
    b.delivery_id as bank_delivery_id
from internal_cash i
full outer join bank_cash b
  on i.statement_date = b.statement_date and i.scenario_id = b.scenario_id
 and i.account_id = b.account_id and i.currency = b.currency
