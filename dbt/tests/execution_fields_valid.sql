select execution_id
from {{ ref('stg_executions') }}
where business_date is null
   or account_id is null
   or instrument_id is null
   or market_ticker is null
   or side not in ('BUY', 'SELL')
   or execution_status not in ('ACTIVE', 'CANCELLED')
   or quantity <= 0
