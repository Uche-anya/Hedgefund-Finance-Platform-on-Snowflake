-- Contractual cash effect of each fill, before fees.
-- A settlement due date is not evidence that payment occurred.
select
    scenario_id,
    delivery_id,
    event_id,
    execution_id,
    business_date,
    executed_at,
    settlement_due,
    fund_id,
    account_id,
    broker_id,
    instrument_id,
    market_ticker,
    side,
    currency,
    quantity,
    execution_price,
    quantity * execution_price as gross_trade_amount,
    case
        when side = 'BUY' then -(quantity * execution_price)
        when side = 'SELL' then quantity * execution_price
    end as expected_cash_change,
    source_file,
    source_row_number
from {{ ref('stg_oms_executions') }}
