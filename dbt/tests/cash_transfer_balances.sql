select *
from {{ ref('fct_cash_daily') }}
where modeled_dividend_cash_to_date is null
   or calculated_cash_balance + unsettled_trade_cash
    <> opening_cash + trade_cash_total + modeled_dividend_cash_to_date
