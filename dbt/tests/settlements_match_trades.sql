with trades as (
    select *
    from {{ ref('stg_activity_events') }}
    where record_type = 'EXECUTION'
),

settlements as (
    select *
    from {{ ref('stg_activity_events') }}
    where record_type = 'SETTLEMENT'
)
select s.event_id
from settlements s left join trades t on s.scenario_id = t.scenario_id and s.execution_id = t.execution_id
where t.event_id is null

      or s.account_id is distinct
   from t.account_id

      or s.instrument_id is distinct
   from t.instrument_id

      or s.currency is distinct
   from t.currency

      or s.side is distinct
   from t.side

      or s.quantity is distinct
   from t.quantity

      or s.cash_amount is distinct
   from (t.quantity * t.execution_price * case when t.side = 'BUY' then -1 else 1 end)

      or to_date(convert_timezone('UTC', s.settled_at)) < t.business_date
