select *
from {{ ref('stg_opening_cash') }}
where opening_cash is null
   or subscription_amount is null
   or opening_cash <> subscription_amount
   or currency <> 'USD'
