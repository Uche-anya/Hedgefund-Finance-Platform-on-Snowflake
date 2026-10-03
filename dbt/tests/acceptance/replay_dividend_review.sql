{{ config(tags=['fixture']) }}
-- Fail if the selected source no longer matches the event we reviewed.
with dividend as (
    select *
    from {{ ref('stg_corporate_actions') }}
    where event_id = 'Ec6372be9137e6a822fd370e8f0738fc31cfb9db56ee95abb2ee9b45f3022db0b'
)
select 'reviewed dividend missing or changed' as problem
from dividend
having count(*) <> 1
    or count_if(ticker = 'MA' and action_type = 'dividends'
        and currency = 'USD' and cash_amount = 0.76
        and ex_dividend_date = '2025-01-10'
        and record_date = '2025-01-10' and pay_date = '2025-02-07') <> 1

union all

-- Keep the lesson within the reviewed calendar and price coverage.
select 'replay extends beyond the reviewed dividend lesson'
from {{ ref('stg_activity_events') }}
where record_type = 'SESSION'
having max(business_date) > '2025-02-07'::date
