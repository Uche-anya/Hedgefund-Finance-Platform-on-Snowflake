{{ config(tags=['fixture']) }}
-- Independently total trades before the ex-date, not the position model.
with expected as (
    select
        scenario_id,
        account_id,
        sum(case when side = 'BUY' then quantity else -quantity end) as shares
    from {{ ref('stg_activity_events') }}
    where record_type = 'EXECUTION'
      and instrument_id = 'MA.US'
      and business_date < '2025-01-10'
    group by scenario_id, account_id
),

actual as (
    select * from {{ ref('fct_dividend_accruals') }}
)
select coalesce(e.account_id, a.account_id) as account_id
from expected e
full outer join actual a
    on e.scenario_id = a.scenario_id and e.account_id = a.account_id
where e.account_id is null or a.account_id is null
    or a.eligible_quantity is distinct from e.shares
    or a.expected_gross_amount is distinct from e.shares * 0.76
    or a.dividend_receivable is distinct from greatest(e.shares * 0.76, 0)
    or a.short_dividend_payable is distinct from greatest(-e.shares * 0.76, 0)
    or a.accrual_date is distinct from '2025-01-10'::date
    or a.reviewed_record_date is distinct from '2025-01-09'::date

union all

select account_id
from actual
group by scenario_id, account_id
having count(*) <> 1

union all

select 'expected two accounts in this January lesson'
from actual
having count(*) <> 2
