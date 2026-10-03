select *
from {{ ref('fct_daily_nav') }}
where simplified_nav is null
   or net_market_value is null
   or gross_exposure is null
   or accrual_basis_cash is null
   or dividend_receivable is null
   or short_dividend_payable is null
   or nav_before_dividends is distinct from accrual_basis_cash + net_market_value
   or simplified_nav is distinct from
       nav_before_dividends + confirmed_dividend_cash + dividend_receivable - short_dividend_payable
   or gross_exposure < abs(net_market_value)
