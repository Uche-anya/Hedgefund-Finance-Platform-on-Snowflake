-- Approval without these fields would be a ticker-only guess.
select instrument_id, provider_ticker
from {{ source('raw', 'security_mappings') }}
where status = 'APPROVED'
  and (provider_cik is null or share_class_figi is null
       or evidence_ref is null or approved_by is null or approved_at is null)
