-- Independent amounts from the five saved execution messages, not close prices.
with expected as (
    select
        column1 as event_id,
        column2 as amount
    from values
        ('sim-event-65bc6285f33a4134b17b24203367e7c6', -2434.80),
        ('sim-event-8390e97e7bd94d8191c6e5703ba059b5', 1120.40),
        ('sim-event-44c36b592f7040ec9eaac440288177c2', -1948.40),
        ('sim-event-bf8211379ba04580a5b707ada1183f9d', -448.52),
        ('sim-event-92010fd009f14e0d95cb85a8b86dfb10', 729.93)
)
select
    e.event_id as expected_event,
    c.*
from expected e
full outer join {{ ref('oms_trade_cash') }} c on e.event_id = c.event_id
where e.event_id is null

      or c.event_id is null

      or c.expected_cash_change <> e.amount

      or c.gross_trade_amount <> abs(e.amount)
