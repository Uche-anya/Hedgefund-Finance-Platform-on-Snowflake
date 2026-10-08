{{ config(tags=['fixture']) }}

with expected as (
    select business_date, account_id, settled_cash_usd,
           trade_receivable_usd, trade_payable_usd
    from {{ ref('cmp_python_account_day') }}
    where ledger_id = '{{ var("comparison_ledger_id") }}'
),
actual as (
    select business_date, account_id, settled_cash_usd,
           trade_receivable_usd, trade_payable_usd,
           count(*) over (partition by business_date, account_id) as key_count
    from {{ ref('fct_account_cash_daily') }}
    where scenario_id = '{{ var("scenario_id") }}'
      and business_date <= (select max(business_date) from expected)
)
select coalesce(a.business_date, e.business_date) as business_date,
       coalesce(a.account_id, e.account_id) as account_id
from actual a full outer join expected e
  on a.business_date = e.business_date and a.account_id = e.account_id
where a.account_id is null or e.account_id is null
   or a.key_count <> 1
   or a.settled_cash_usd is null or a.trade_receivable_usd is null
   or a.trade_payable_usd is null
   or abs(a.settled_cash_usd - e.settled_cash_usd) > 0.000001
   or abs(a.trade_receivable_usd - e.trade_receivable_usd) > 0.000001
   or abs(a.trade_payable_usd - e.trade_payable_usd) > 0.000001
