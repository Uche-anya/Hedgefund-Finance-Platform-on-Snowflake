{{ config(tags=['fixture']) }}
select account_id, ticker, timeliness_status
from {{ ref('fct_position_reconciliation') }}
where broker_quantity is not null
  and timeliness_status <> case when account_id = 'SIM-REPLAY-02' then 'LATE' else 'ON_TIME' end
