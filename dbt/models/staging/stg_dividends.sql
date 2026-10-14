-- Take the latest delivered version of each event. A review of an old
-- version cannot approve a provider correction with changed terms.
with received as (
    select r.payload, r.source_file, r.loaded_at,
        d.delivery_id, d.business_date as snapshot_date, d.registered_at
    from {{ source('raw', 'daily_dividend_events') }} r
    join {{ source('raw', 'daily_deliveries') }} d
        on d.source_name = 'dividends'
        and d.scenario_id = 'massive'
        and d.status = 'LOADED'
        and d.business_date <= to_date('{{ var("business_date") }}')
        and endswith(r.source_file, d.stage_path)
), current_events as (
    select
        payload:id::varchar as event_id,
        payload:ticker::varchar as ticker,
        try_to_date(payload:ex_dividend_date::varchar) as ex_dividend_date,
        try_to_date(payload:record_date::varchar) as record_date,
        try_to_date(payload:pay_date::varchar) as pay_date,
        try_to_decimal(payload:cash_amount::varchar, 38, 12) as cash_amount,
        payload:currency::varchar as currency,
        payload:distribution_type::varchar as distribution_type,
        sha2(to_json(array_construct(
            payload:id, payload:ticker, payload:ex_dividend_date,
            payload:record_date, payload:pay_date, payload:cash_amount,
            payload:currency, payload:distribution_type
        )), 256) as terms_hash,
        delivery_id, snapshot_date, source_file, loaded_at
    from received
    qualify row_number() over (
        partition by payload:id::varchar
        order by snapshot_date desc, registered_at desc, delivery_id desc,
            loaded_at desc, source_file desc
    ) = 1
), last_review as (
    select event_id, terms_hash, decision, instrument_id, reviewer, reason,
        reviewed_at, review_id
    from {{ source('raw', 'dividend_reviews') }}
    qualify row_number() over (
        partition by event_id, terms_hash
        order by reviewed_at desc, review_id desc
    ) = 1
)
select e.*,
    coalesce(r.decision, 'PENDING') as review_status,
    r.instrument_id, r.reviewer, r.reason as review_reason, r.reviewed_at
from current_events e
left join last_review r
    on r.event_id = e.event_id and r.terms_hash = e.terms_hash
