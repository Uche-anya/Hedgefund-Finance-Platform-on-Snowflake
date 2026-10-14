-- Only fund-universe events reach this queue. A ticker is a candidate,
-- not proof of the security's identity.
with matches as (
    select e.event_id,
        count(*) as mapping_count,
        max(m.instrument_id) as mapped_instrument_id,
        max(m.status) as mapping_status,
        max(m.provider_cik) as provider_cik,
        max(m.share_class_figi) as share_class_figi
    from {{ ref('stg_dividends') }} e
    join {{ source('raw', 'security_mappings') }} m
        on m.provider_ticker = e.ticker
        and e.ex_dividend_date >= m.valid_from
        and (m.valid_to is null or e.ex_dividend_date <= m.valid_to)
    group by e.event_id
)
select
    e.event_id, e.terms_hash, e.ticker, e.ex_dividend_date, e.pay_date,
    e.cash_amount, e.currency, e.distribution_type, e.terms_changed,
    e.missing_from_latest_snapshot,
    e.review_status, e.instrument_id as reviewed_instrument_id,
    m.mapped_instrument_id as instrument_id, m.mapping_status,
    m.provider_cik, m.share_class_figi, e.delivery_id,
    case
        when m.mapping_count <> 1 then 'AMBIGUOUS_MAPPING'
        when e.review_status = 'REJECTED' then 'REJECTED'
        when e.missing_from_latest_snapshot then 'MISSING_FROM_SNAPSHOT'
        when coalesce(m.mapping_status, '') <> 'APPROVED'
            then 'SECURITY_REVIEW'
        when e.review_status = 'APPROVED'
             and e.instrument_id <> m.mapped_instrument_id
            then 'IDENTITY_CONFLICT'
        when e.ex_dividend_date is null or e.cash_amount is null
             or e.cash_amount <= 0 or e.currency <> 'USD'
            then 'INVALID_TERMS'
        when e.review_status = 'APPROVED' then 'READY'
        when e.terms_changed then 'TERMS_REVIEW'
        when coalesce(e.distribution_type, '') <> 'recurring'
            then 'EVENT_REVIEW'
        else 'READY'
    end as processing_status
from {{ ref('stg_dividends') }} e
join matches m on m.event_id = e.event_id
