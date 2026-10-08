{{ config(tags=['fixture']) }}

with expected as (
    select business_date, account_id, reviewed_nav_usd, illustrative_nav_usd,
           pending_candidate_impact_usd, reviewed_dividend_receivable_usd,
           reviewed_short_dividend_payable_usd
    from {{ ref('cmp_python_account_day') }}
    where ledger_id = '{{ var("comparison_ledger_id") }}'
),
actual as (
    select business_date, account_id, reviewed_nav_usd, illustrative_nav_usd,
           pending_candidate_impact_usd, reviewed_dividend_receivable_usd,
           reviewed_short_dividend_payable_usd,
           count(*) over (partition by business_date, account_id) as key_count
    from {{ ref('fct_account_nav_daily') }}
    where scenario_id = '{{ var("scenario_id") }}'
      and business_date <= (select max(business_date) from expected)
)
select coalesce(a.business_date, e.business_date) as business_date,
       coalesce(a.account_id, e.account_id) as account_id
from actual a full outer join expected e
  on a.business_date = e.business_date and a.account_id = e.account_id
where a.account_id is null or e.account_id is null
   or a.key_count <> 1
   or a.reviewed_nav_usd is null or a.illustrative_nav_usd is null
   or a.pending_candidate_impact_usd is null
   or a.reviewed_dividend_receivable_usd is null
   or a.reviewed_short_dividend_payable_usd is null
   or abs(a.reviewed_nav_usd - e.reviewed_nav_usd) > 0.000001
   or abs(a.illustrative_nav_usd - e.illustrative_nav_usd) > 0.000001
   or abs(a.pending_candidate_impact_usd - e.pending_candidate_impact_usd) > 0.000001
   or abs(a.reviewed_dividend_receivable_usd
          - e.reviewed_dividend_receivable_usd) > 0.000001
   or abs(a.reviewed_short_dividend_payable_usd
          - e.reviewed_short_dividend_payable_usd) > 0.000001
