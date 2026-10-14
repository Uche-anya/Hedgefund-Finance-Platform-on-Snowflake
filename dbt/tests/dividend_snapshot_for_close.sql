-- The dbt run must see the dividend delivery for its close date.
select to_date('{{ var("business_date") }}') as business_date
where not exists (
    select 1
    from {{ ref('stg_dividends') }}
    where snapshot_date = to_date('{{ var("business_date") }}')
)
