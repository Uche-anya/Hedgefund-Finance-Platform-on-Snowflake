-- Read one load and apply the saved BNY and TEL decisions.
with actions as (
    select *
    from {{ source('raw', 'corporate_actions') }}
    where load_id = '{{ var("corporate_action_load_id") }}'
),

reviews as (
    select
        payload,
        snapshot_id,
        load_id,
        source_file,
        source_row_number,
        loaded_at
    from {{ source('raw', 'corporate_action_reviews') }}
    where load_id = '{{ var("corporate_action_load_id") }}'
),

replacements as (
    select *
    from reviews
    where payload:decision:decision::varchar = 'ONE_CASH_ENTITLEMENT'
),

replaced_ids as (
    select
        r.snapshot_id,
        f.value:event:id::varchar as event_id
    from replacements r, lateral flatten(input => r.payload:decision:source_records) f
),

decisions as (
    select
        snapshot_id,
        payload:decision:event_id::varchar as event_id,
        payload:decision:decision::varchar as decision,
        payload:decision:reason::varchar as reason,
        payload:decision:target_instrument::varchar as target_instrument,
        payload as review_evidence
    from reviews
    where payload:decision:event_id is not null
),

selected as (
    select
        a.payload:event as event,
        a.payload:action_type::varchar as action_type,
        a.payload:event:id::varchar as event_id,
        array_construct(a.payload:event:id::varchar) as source_event_ids,
        coalesce(d.decision, 'NEEDS_REVIEW') as review_decision,
        d.reason as review_reason,
        d.review_evidence,
        a.payload as source_payload,
        a.snapshot_id,
        a.load_id,
        a.source_file,
        a.source_row_number,
        a.loaded_at
    from actions a
    left join decisions d
        on a.snapshot_id = d.snapshot_id
        and a.payload:event:id::varchar = d.event_id
    where not (coalesce(d.decision, '') = 'EXCLUDED_FROM_BANK'
               and coalesce(d.target_instrument, '') = 'US_BNY_MELLON_COMMON')
      and not exists (
          select 1
          from replaced_ids x
          where x.snapshot_id = a.snapshot_id
            and x.event_id = a.payload:event:id::varchar
      )

    union all

    select
        r.payload:decision:event,
        'dividends',
        r.payload:decision:reviewed_event_id::varchar,
        r.payload:review_manifest:source_event_ids,
        'ONE_CASH_ENTITLEMENT',
        r.payload:decision:reason::varchar,
        r.payload,
        r.payload:decision:source_records,
        r.snapshot_id,
        r.load_id,
        r.source_file,
        r.source_row_number,
        r.loaded_at
    from replacements r
)
select
    event_id,
    action_type,
    event:ticker::varchar as ticker,
    try_to_date(event:ex_dividend_date::varchar, 'YYYY-MM-DD') as ex_dividend_date,
    try_to_date(event:execution_date::varchar, 'YYYY-MM-DD') as execution_date,
    try_to_date(event:record_date::varchar, 'YYYY-MM-DD') as record_date,
    try_to_date(event:pay_date::varchar, 'YYYY-MM-DD') as pay_date,
    try_to_date(event:declaration_date::varchar, 'YYYY-MM-DD') as declaration_date,
    event:currency::varchar as currency,
    case when regexp_like(event:cash_amount::varchar, '^[0-9]{1,26}([.][0-9]{1,12})?$')
        then try_to_decimal(event:cash_amount::varchar, 38, 12) end as cash_amount,
    case when regexp_like(event:split_from::varchar, '^[0-9]{1,26}([.][0-9]{1,12})?$')
        then try_to_decimal(event:split_from::varchar, 38, 12) end as split_from,
    case when regexp_like(event:split_to::varchar, '^[0-9]{1,26}([.][0-9]{1,12})?$')
        then try_to_decimal(event:split_to::varchar, 38, 12) end as split_to,
    event:distribution_type::varchar as distribution_type,
    event:adjustment_type::varchar as adjustment_type,
    review_decision,
    review_reason,
    'SECURITY_IDENTITY_AND_ACCOUNT_ELIGIBILITY_REQUIRE_REVIEW' as accounting_status,
    source_event_ids,
    review_evidence,
    source_payload,
    event as event_raw,
    snapshot_id,
    load_id,
    source_file,
    source_row_number,
    loaded_at
from selected
