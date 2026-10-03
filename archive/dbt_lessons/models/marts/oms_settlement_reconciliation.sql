-- Historical replay cutoff uses source publication time, not today's load time.
with confirmations as (
    select *
    from {{ ref('stg_settlements') }}
    where published_at <= '{{ var("settlement_cutoff") }}'::timestamp_tz
      and settled_at <= '{{ var("settlement_cutoff") }}'::timestamp_tz
),

trades as (
    select *
    from {{ ref('oms_trade_cash') }}
    where executed_at <= '{{ var("settlement_cutoff") }}'::timestamp_tz
)
select
    coalesce(t.scenario_id, s.scenario_id) as scenario_id,
    coalesce(t.execution_id, s.execution_id) as execution_id,
    coalesce(t.account_id, s.account_id) as account_id,
    coalesce(t.instrument_id, s.instrument_id) as instrument_id,
    coalesce(t.side, s.side) as side,
    t.currency as expected_currency,
    s.currency as confirmed_currency,
    t.quantity as expected_quantity,
    s.settled_quantity,
    t.expected_cash_change,
    s.cash_amount as confirmed_cash_change,
    s.cash_amount - t.expected_cash_change as cash_difference,
    t.settlement_due,
    s.settlement_date,
    s.settled_at,
    s.published_at as confirmation_published_at,
    s.event_id as confirmation_event_id,
    t.delivery_id as oms_delivery_id,
    s.delivery_id as settlement_delivery_id,
    s.source_file as confirmation_file,
    '{{ var("settlement_cutoff") }}'::timestamp_tz as as_of,
    case
        when t.event_id is null then 'UNEXPECTED_CONFIRMATION'
        when s.event_id is null then 'NO_CONFIRMATION'
        when t.fund_id <> s.fund_id

             or t.account_id <> s.account_id

             or t.broker_id <> s.broker_id

             or t.instrument_id <> s.instrument_id

             or t.side <> s.side

             or t.currency <> s.currency

             or t.quantity <> s.settled_quantity

             or t.expected_cash_change <> s.cash_amount then 'DETAILS_MISMATCH'
        else 'MATCHED'
    end as reconciliation_status
from trades t
full outer join confirmations s
    on t.scenario_id = s.scenario_id
    and t.execution_id = s.execution_id
