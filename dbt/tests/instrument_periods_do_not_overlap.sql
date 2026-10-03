select a.security_id, b.security_id
from {{ ref('dim_instrument') }} a
join {{ ref('dim_instrument') }} b
  on a.ticker = b.ticker
 and a.security_id < b.security_id
 and a.valid_from <= b.valid_to
 and b.valid_from <= a.valid_to
