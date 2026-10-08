{{ config(tags=['fixture']) }}

-- The Snowflake calculation must reproduce every saved position in ledger 003.
with expected as (
    select business_date, account_id, security_id, quantity,
           close_price_usd, market_value_usd
    from {{ ref('cmp_python_position_day') }}
    where ledger_id = '{{ var("comparison_ledger_id") }}'
),
actual as (
    select business_date, account_id, security_id, quantity,
           close_price_usd, market_value_usd,
           count(*) over (partition by business_date, account_id, security_id)
               as key_count
    from {{ ref('fct_account_positions_daily') }}
    where scenario_id = '{{ var("scenario_id") }}'
      and business_date <= (select max(business_date) from expected)
)
select coalesce(a.business_date, e.business_date) as business_date,
       coalesce(a.account_id, e.account_id) as account_id,
       coalesce(a.security_id, e.security_id) as security_id
from actual a
full outer join expected e
  on a.business_date = e.business_date
 and a.account_id = e.account_id
 and a.security_id = e.security_id
where a.security_id is null or e.security_id is null
   or a.key_count <> 1
   or a.quantity is null or a.close_price_usd is null or a.market_value_usd is null
   or a.quantity <> e.quantity
   or abs(a.close_price_usd - e.close_price_usd) > 0.000001
   or abs(a.market_value_usd - e.market_value_usd) > 0.000001
