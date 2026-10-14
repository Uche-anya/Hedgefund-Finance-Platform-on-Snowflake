-- Take the latest delivered version of each event. A review of an old
-- version cannot approve a provider correction with changed terms.
with latest_delivery as (
    select delivery_id, business_date
    from {{ source('raw', 'daily_deliveries') }}
    where source_name = 'dividends' and scenario_id = 'massive'
      and status = 'LOADED'
      and business_date <= to_date('{{ var("business_date") }}')
    qualify row_number() over (
        order by business_date desc, registered_at desc, delivery_id desc
    ) = 1
), received as (
    select r.payload, r.source_file, r.loaded_at,
        d.delivery_id, d.business_date as snapshot_date, d.registered_at
    from {{ source('raw', 'daily_dividend_events') }} r
    join {{ source('raw', 'daily_deliveries') }} d
        on d.source_name = 'dividends'
        and d.scenario_id = 'massive'
        and d.status = 'LOADED'
        and d.business_date <= to_date('{{ var("business_date") }}')
        and endswith(r.source_file, d.stage_path)
), typed as (
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
        delivery_id, snapshot_date, registered_at, source_file, loaded_at
    from received
), current_events as (
    select *, count(distinct terms_hash) over (partition by event_id) > 1
        as terms_changed
    from typed
    qualify row_number() over (
        partition by event_id
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
    e.delivery_id <> l.delivery_id
      and e.ex_dividend_date between dateadd(day, -30, l.business_date)
                                 and dateadd(day, 45, l.business_date)
        as missing_from_latest_snapshot,
    coalesce(r.decision, 'PENDING') as review_status,
    r.instrument_id, r.reviewer, r.reason as review_reason, r.reviewed_at
from current_events e
cross join latest_delivery l
left join last_review r
    on r.event_id = e.event_id and r.terms_hash = e.terms_hash
