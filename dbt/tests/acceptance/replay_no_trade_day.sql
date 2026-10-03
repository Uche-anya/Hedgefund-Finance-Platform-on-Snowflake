{{ config(tags=['fixture']) }}
select *
from {{ ref('fct_daily_positions') }}
where business_date = '2025-01-15'::date
  and (trade_count <> 0 or net_trade_quantity <> 0)
