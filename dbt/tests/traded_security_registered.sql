-- An OMS instrument needs a dated candidate even if it is not approved yet.
select distinct e.instrument_id, e.market_ticker
from {{ ref('stg_executions') }} e
where not exists (
    select 1
    from {{ source('raw', 'security_mappings') }} m
    where m.instrument_id = e.instrument_id
      and m.provider_ticker = e.market_ticker
      and e.business_date >= m.valid_from
      and (m.valid_to is null or e.business_date <= m.valid_to)
)
