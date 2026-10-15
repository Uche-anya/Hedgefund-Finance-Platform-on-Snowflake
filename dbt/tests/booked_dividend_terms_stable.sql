-- A provider correction after booking needs a reviewed restatement.
select e.event_id, e.account_id, e.terms_hash
from {{ ref('fct_dividend_exposure') }} e
left join {{ ref('dividend_review_queue') }} q
    on q.event_id = e.event_id
where e.scenario_id = '{{ var("scenario_id") }}'
  and e.ex_dividend_date <= to_date('{{ var("business_date") }}')
  and (q.event_id is null or q.terms_hash <> e.terms_hash
       or q.processing_status <> 'READY')
