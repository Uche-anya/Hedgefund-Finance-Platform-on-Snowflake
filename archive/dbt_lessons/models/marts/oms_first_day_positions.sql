-- This scenario starts with no holdings. These are trade-date positions,
-- not confirmation that the shares and cash have settled.
with movements as (
    select
        scenario_id,
        business_date,
        fund_id,
        account_id,
        instrument_id,
        market_ticker,
        currency,
        sum(case
            when side = 'BUY' then quantity
            when side = 'SELL' then -quantity
        end) as net_trade_quantity
    from {{ ref('stg_oms_executions') }}
    group by scenario_id, business_date, fund_id, account_id,
        instrument_id, market_ticker, currency
)
select
    movements.*,
    0::number(38, 9) as opening_quantity,
    net_trade_quantity as closing_quantity
from movements
