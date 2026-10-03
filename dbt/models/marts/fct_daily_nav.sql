-- Dividend settlement moves the expected amount into cash without new income.
with values_by_account as (
    select
        scenario_id,
        business_date,
        account_id,
        currency,
        sum(market_value) as net_market_value,
        sum(abs(market_value)) as gross_exposure
    from {{ ref('fct_daily_valuations') }}
    group by scenario_id, business_date, account_id, currency
)
select
    c.*,
    v.net_market_value,
    v.gross_exposure,
    c.reported_settled_cash - c.confirmed_dividend_cash + c.receivables - c.payables
        - c.expense_payable + v.net_market_value
        as nav_before_dividends,
    nav_before_dividends + c.confirmed_dividend_cash
        + c.dividend_receivable - c.short_dividend_payable
        as simplified_nav,
    'EQUITY_CASH_SETTLEMENTS_DIVIDENDS_FLOWS_AND_EXPENSES' as calculation_basis
from {{ ref('fct_daily_cash') }} c
left join values_by_account v
    on c.scenario_id = v.scenario_id and c.business_date = v.business_date
    and c.account_id = v.account_id and c.currency = v.currency
