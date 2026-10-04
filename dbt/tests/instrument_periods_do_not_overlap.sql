select a.instrument_version_id, b.instrument_version_id
from {{ ref('dim_instrument') }} a
join {{ ref('dim_instrument') }} b
  on a.instrument_version_id < b.instrument_version_id
 and (a.security_id = b.security_id or a.ticker = b.ticker)
 and a.valid_from <= b.valid_to
 and b.valid_from <= a.valid_to
