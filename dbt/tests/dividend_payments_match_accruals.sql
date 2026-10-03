-- This feed records one full gross payment per account and event.
select p.event_id
from {{ ref('stg_activity_events') }} p
left join {{ ref('fct_dividend_accruals') }} a
    on p.scenario_id = a.scenario_id and p.account_id = a.account_id
    and p.corporate_action_id = a.event_id
where p.record_type = 'DIVIDEND_PAYMENT'
  and (a.event_id is null
       or coalesce(trim(p.event_id), '') = ''
       or coalesce(trim(p.source_system), '') = ''
       or p.instrument_id is distinct from a.instrument_id
       or p.currency is distinct from a.currency
       or p.cash_amount is distinct from a.expected_gross_amount
       or p.cash_amount = 0
       or p.settled_at is null or p.published_at is null
       or p.published_at < p.settled_at
       or p.business_date is distinct from to_date(convert_timezone('UTC', p.settled_at))
       or p.business_date < a.accrual_date)
