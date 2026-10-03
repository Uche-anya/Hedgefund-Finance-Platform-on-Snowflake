-- An empty source must not result in a falsely successful empty build.
select 'executions' as missing_source
where not exists (select 1
from {{ ref('stg_executions') }})
union all
select 'allocations'
where not exists (select 1
from {{ ref('stg_allocations') }})
