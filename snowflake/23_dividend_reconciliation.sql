-- Read-only report for the February 7 replay cutoff.
-- A missing confirmation is not proof of a failed payment.
with reporting_session as (
    select scenario_id, business_date, cutoff
    from NORTHBRIDGE_DEV.DBT_DEV.STG_ACTIVITY_EVENTS
    where record_type = 'SESSION' and business_date = '2025-02-07'
),

compared as (
    select
        s.business_date,
        s.cutoff,
        a.scenario_id,
        a.account_id,
        a.event_id as corporate_action_id,
        a.instrument_id,
        a.currency,
        a.scheduled_pay_date,
        a.expected_gross_amount,
        count(p.event_id) as confirmation_count,
        coalesce(sum(p.cash_amount), 0) as confirmed_amount,
        max(p.published_at) as latest_confirmation_at
    from reporting_session s
    join NORTHBRIDGE_DEV.DBT_DEV.REPLAY_DIVIDEND_ACCRUALS a
        on s.scenario_id = a.scenario_id and s.business_date >= a.accrual_date
    left join NORTHBRIDGE_DEV.DBT_DEV.STG_ACTIVITY_EVENTS p
        on p.record_type = 'DIVIDEND_PAYMENT'
        and p.scenario_id = a.scenario_id and p.account_id = a.account_id
        and p.corporate_action_id = a.event_id
        and p.instrument_id = a.instrument_id and p.currency = a.currency
        and p.settled_at <= s.cutoff and p.published_at <= s.cutoff
    group by s.business_date, s.cutoff, a.scenario_id, a.account_id,
        a.event_id, a.instrument_id, a.currency, a.scheduled_pay_date,
        a.expected_gross_amount
)
select
    *,
    case when expected_gross_amount < 0 then 'PAYMENT_OUT' else 'RECEIPT_IN' end as direction,
    expected_gross_amount - confirmed_amount as outstanding_amount,
    case
        when confirmation_count > 1 then 'REVIEW_MULTIPLE_CONFIRMATIONS'
        when confirmation_count = 1 and confirmed_amount = expected_gross_amount then 'MATCHED'
        when confirmation_count = 1 then 'AMOUNT_MISMATCH'
        when business_date < scheduled_pay_date then 'AWAITING_SCHEDULED_DATE'
        else 'NO_CONFIRMATION'
    end as reconciliation_status
from compared
order by account_id, corporate_action_id;
