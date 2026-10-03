with checked as (
    select *, count(*) over (partition by record_id) as record_count
    from {{ ref('stg_bank_cash_statements') }}
)
select * from checked
where record_count <> 1
   or record_id is null or statement_id is null or scenario_id is null
   or statement_date is null or account_id is null or currency <> 'USD'
   or closing_balance is null or published_at is null
