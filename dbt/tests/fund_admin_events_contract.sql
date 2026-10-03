with checked as (
    select *, count(*) over (partition by record_id) as record_count
    from {{ ref('stg_fund_admin_events') }}
)
select * from checked
where record_count <> 1
   or record_id is null or scenario_id is null or event_date is null
   or account_id is null or currency <> 'USD' or amount is null
   or event_type not in ('INVESTOR_SUBSCRIPTION', 'INVESTOR_REDEMPTION', 'EXPENSE')
   or (event_type = 'INVESTOR_SUBSCRIPTION' and amount <= 0)
   or (event_type = 'INVESTOR_REDEMPTION' and amount >= 0)
   or (event_type = 'EXPENSE' and (amount <= 0 or payment_date < event_date))
