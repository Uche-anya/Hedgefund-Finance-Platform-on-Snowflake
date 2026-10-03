{{ config(tags=['fixture']) }}
with expected(account_id, ticker, book_status, internal_quantity, broker_quantity) as (
    select * from values
        ('SIM-REPLAY-01', 'AMZN', 'QUANTITY_MISMATCH', 1018::number, 1021::number),
        ('SIM-REPLAY-02', 'MSFT', 'MISSING_AT_BROKER', 487::number, null::number),
        ('SIM-REPLAY-03', 'AAPL', 'UNEXPECTED_AT_BROKER', null::number, 12::number)
),
actual as (
    select account_id, ticker, book_status, internal_quantity, broker_quantity
    from {{ ref('fct_position_reconciliation') }}
    where book_status <> 'MATCHED'
)
select
    coalesce(e.account_id, a.account_id) as account_id,
    coalesce(e.ticker, a.ticker) as ticker
from expected e
full outer join actual a
  on e.account_id = a.account_id and e.ticker = a.ticker
where e.account_id is null
   or a.account_id is null
   or e.book_status <> a.book_status
   or not equal_null(e.internal_quantity, a.internal_quantity)
   or not equal_null(e.broker_quantity, a.broker_quantity)
