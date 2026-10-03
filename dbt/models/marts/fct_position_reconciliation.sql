with internal_book as (
    select
        business_date as statement_date,
        account_id,
        security_id,
        market_ticker as ticker,
        currency,
        closing_quantity as internal_quantity
    from {{ ref('fct_daily_positions') }}
    where business_date = '{{ var("broker_statement_date") }}'
),

broker_book as (
    select
        statement_date,
        account_id,
        security_id,
        mastered_ticker as ticker,
        currency,
        quantity as broker_quantity,
        statement_id,
        broker_id,
        published_at,
        delivery_id
    from {{ ref('stg_broker_positions') }}
)
select
    coalesce(i.statement_date, b.statement_date) as statement_date,
    coalesce(i.account_id, b.account_id) as account_id,
    coalesce(i.security_id, b.security_id) as security_id,
    coalesce(i.ticker, b.ticker) as ticker,
    coalesce(i.currency, b.currency) as currency,
    i.internal_quantity,
    b.broker_quantity,
    b.broker_quantity - i.internal_quantity as quantity_difference,
    case
        when i.security_id is null then 'UNEXPECTED_AT_BROKER'
        when b.security_id is null then 'MISSING_AT_BROKER'
        when i.internal_quantity <> b.broker_quantity then 'QUANTITY_MISMATCH'
        else 'MATCHED'
    end as book_status,
    case
        when b.security_id is null then 'NO_BROKER_RECORD'
        when b.published_at > '{{ var("broker_expected_by") }}'::timestamp_tz then 'LATE'
        else 'ON_TIME'
    end as timeliness_status,
    b.statement_id,
    b.broker_id,
    b.published_at,
    b.delivery_id as broker_delivery_id
from internal_book i
full outer join broker_book b
  on i.statement_date = b.statement_date
 and i.account_id = b.account_id
 and i.security_id = b.security_id
 and i.currency = b.currency
