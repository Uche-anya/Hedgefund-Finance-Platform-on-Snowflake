-- An approval needs a reviewed security, plausible terms and a named reviewer.
select event_id, terms_hash
from {{ ref('stg_dividends') }}
where review_status = 'APPROVED'
  and (instrument_id is null or reviewer is null
       or ex_dividend_date is null or cash_amount <= 0
       or currency <> 'USD')
