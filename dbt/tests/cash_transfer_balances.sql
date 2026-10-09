select *
from {{ ref('fct_cash_daily') }}
where calculated_cash_balance + unsettled_trade_cash
    <> opening_cash + trade_cash_total
