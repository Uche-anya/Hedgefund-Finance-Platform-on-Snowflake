{{ config(tags=['fixture']) }}
select count(*) as actual_rows
from {{ ref('stg_broker_positions') }}
having count(*) <> 40
