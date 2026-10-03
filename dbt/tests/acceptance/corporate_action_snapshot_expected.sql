{{ config(tags=['fixture']) }}
select
    count(*) as actual_rows,
    count_if(review_decision = 'KEEP_SEPARATE_COMPONENTS') as separate_components,
    count_if(review_decision = 'ONE_CASH_ENTITLEMENT') as combined_entitlements
from {{ ref('stg_corporate_actions') }}
having count(*) <> 3253
    or count_if(review_decision = 'KEEP_SEPARATE_COMPONENTS') <> 18
    or count_if(review_decision = 'ONE_CASH_ENTITLEMENT') <> 1
    or count_if(ticker = 'TEL' and ex_dividend_date = '2024-11-22' and cash_amount = 0.65) <> 1
    or count_if(ticker = 'BNY' and ex_dividend_date < '2026-05-21') <> 0
