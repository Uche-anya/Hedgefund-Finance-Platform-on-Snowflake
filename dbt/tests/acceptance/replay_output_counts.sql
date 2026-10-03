{{ config(tags=['fixture']) }}
select
    'positions' as output,
    count(*) as records
from {{ ref('fct_daily_positions') }}
having count(*) <> 920
union all
select
    'valuation',
    count(*)
from {{ ref('fct_daily_valuations') }}
having count(*) <> 920
union all
select
    'cash',
    count(*)
from {{ ref('fct_daily_cash') }}
having count(*) <> 46
union all
select
    'nav',
    count(*)
from {{ ref('fct_daily_nav') }}
having count(*) <> 46
