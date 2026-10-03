-- Independently calculated from the five saved trades:
-- Apple: 10 + 8 - 3 = 15. Amazon: -5 + 2 = -3.
with expected as (
    select
        'AAPL.US' as instrument_id,
        'AAPL' as market_ticker,
        15 as quantity

    union all

    select
        'AMZN.US',
        'AMZN',
        -3
)
select
    e.instrument_id as expected_instrument,
    p.*
from expected e
full outer join {{ ref('oms_first_day_positions') }} p
    on e.instrument_id = p.instrument_id
where e.instrument_id is null

      or p.instrument_id is null

      or p.market_ticker <> e.market_ticker

      or p.currency <> 'USD'

      or p.opening_quantity <> 0

      or p.net_trade_quantity <> e.quantity

      or p.closing_quantity <> e.quantity
