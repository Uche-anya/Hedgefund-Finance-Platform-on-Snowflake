with keys as (
    select
        record_type,
        case when record_type = 'DIVIDEND_PAYMENT'
             then account_id || '/' || corporate_action_id
             else coalesce(execution_id, account_id, business_date_raw) end as business_key
    from {{ ref('stg_activity_events') }}
)
select
    record_type,
    business_key,
    count(*) as rows_received
from keys
group by record_type, business_key
having count(*) > 1
