-- A held stock's ex-date cannot pass the close without a reviewed booking.
with prior_close as (
    select max(p.valuation_date) as valuation_date
    from {{ ref('fct_position_daily') }} p
    join {{ source('raw', 'daily_close_runs') }} r
        on r.business_date = p.valuation_date
        and r.scenario_id = p.scenario_id
        and r.status = 'VALIDATED'
    where p.scenario_id = '{{ var("scenario_id") }}'
      and p.valuation_date < to_date('{{ var("business_date") }}')
)
select q.event_id, q.processing_status, p.account_id
from {{ ref('dividend_review_queue') }} q
join {{ ref('fct_position_daily') }} p
    on p.valuation_date = (select valuation_date from prior_close)
    and p.scenario_id = '{{ var("scenario_id") }}'
    and p.instrument_id = q.instrument_id
    and p.shares <> 0
left join {{ ref('fct_dividend_exposure') }} e
    on e.event_id = q.event_id
    and e.scenario_id = p.scenario_id
    and e.account_id = p.account_id
where q.ex_dividend_date = to_date('{{ var("business_date") }}')
  and (q.processing_status <> 'READY' or e.event_id is null)
