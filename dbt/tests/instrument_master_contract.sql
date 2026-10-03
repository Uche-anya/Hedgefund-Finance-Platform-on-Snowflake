select security_id
from {{ ref('dim_instrument') }}
where security_id is null
   or ticker is null
   or share_class_figi is null
   or reviewed_issuer_cik is null
   or currency <> 'USD'
   or security_type <> 'CS'
   or valid_from is null
   or valid_to is null
   or valid_from > valid_to
