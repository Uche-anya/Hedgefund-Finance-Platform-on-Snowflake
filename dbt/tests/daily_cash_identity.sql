-- Settling a trade moves an obligation into cash; it cannot change their total.
select *
from {{ ref('fct_daily_cash') }}
where reported_settled_cash is null
   or receivables is null
   or payables is null
   or trade_date_cash is null

      or reported_settled_cash - confirmed_dividend_cash + receivables - payables
          - expense_payable <> accrual_basis_cash

      or receivables < 0
      or payables < 0
   or confirmed_dividend_cash is null
   or dividend_receivable is null or dividend_receivable < 0
   or short_dividend_payable is null or short_dividend_payable < 0
   or expense_payable is null or expense_payable < 0
