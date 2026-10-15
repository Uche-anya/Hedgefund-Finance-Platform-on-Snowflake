select valuation_date, scenario_id, account_id
from {{ ref('fct_nav_daily') }}
where dividend_receivable_usd is null
   or dividend_liability_usd is null
   or dividend_pnl_usd is null
   or nav_usd <> calculated_cash_balance + unsettled_trade_cash
    + position_value + dividend_receivable_usd - dividend_liability_usd
