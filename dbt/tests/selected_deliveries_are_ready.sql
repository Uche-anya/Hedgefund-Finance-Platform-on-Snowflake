with expected as (
    select column1 as source_name, column2 as delivery_id
    from values
        ('activity_events', '{{ var("replay_delivery_id") }}'),
        ('historical_prices', '{{ var("historical_price_delivery_id") }}'),
        ('corporate_actions', '{{ var("corporate_action_load_id") }}'),
        ('broker_positions', '{{ var("broker_delivery_id") }}'),
        ('fx_rates', '{{ var("fx_delivery_id") }}'),
        ('treasury_rates', '{{ var("treasury_delivery_id") }}'),
        ('fund_admin', '{{ var("fund_admin_delivery_id") }}'),
        ('bank_cash', '{{ var("bank_delivery_id") }}')
),
registered as (
    select source_name, delivery_id, delivery_status, expected_rows, received_rows,
           count(*) over (partition by source_name, delivery_id) as registrations
    from {{ source('operations', 'deliveries') }}
)
select e.source_name, e.delivery_id
from expected e
left join registered r
  on e.source_name = r.source_name and e.delivery_id = r.delivery_id
where r.delivery_id is null
   or r.delivery_status <> 'READY'
   or r.expected_rows <> r.received_rows
   or r.registrations <> 1
