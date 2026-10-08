-- One active execution and its settlement, if the custodian has confirmed it.
with trades as (
    select scenario_id, account_id, execution_id, business_date,
           case when side = 'BUY' then -quantity * execution_price
                else quantity * execution_price end as expected_cash_usd
    from {{ ref('stg_oms_events') }}
    where scenario_id = '{{ var("scenario_id") }}'
      and execution_status = 'ACTIVE'
),
settlements as (
    select scenario_id, account_id, execution_id, settlement_date,
           cash_amount
    from {{ ref('stg_settlement_events') }}
    where scenario_id = '{{ var("scenario_id") }}'
      and settlement_status = 'SETTLED'
)
select t.*, s.settlement_date, s.cash_amount
from trades t
left join settlements s
  on t.scenario_id = s.scenario_id and t.account_id = s.account_id
 and t.execution_id = s.execution_id
