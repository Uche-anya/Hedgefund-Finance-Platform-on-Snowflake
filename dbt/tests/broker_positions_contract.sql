select 'invalid required field' as issue
where exists (
    select 1
    from {{ ref('stg_broker_positions') }}
    where record_id is null
       or statement_id is null
       or statement_date is null
       or account_id is null
       or broker_instrument_id is null
       or security_id is null
       or currency <> 'USD'
       or quantity is null
       or published_at is null
       or position_basis <> 'TRADE_DATE'
       or coalesce(trim(source_system), '') = ''
       or is_simulated is null
)

union all

select 'duplicate record id'
where exists (
    select record_id
    from {{ ref('stg_broker_positions') }}
    group by record_id
    having count(*) > 1
)
