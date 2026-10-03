{{ config(materialized='incremental', incremental_strategy='append', full_refresh=false) }}
-- Save each scenario/cutoff once. A replay must not rewrite an earlier report.
select
    r.*,
    current_timestamp() as captured_at
from {{ ref('oms_settlement_reconciliation') }} r
{% if is_incremental() %}
where not exists (
    select 1
    from {{ this }} saved
    where saved.scenario_id = r.scenario_id and saved.as_of = r.as_of
)
{% endif %}
