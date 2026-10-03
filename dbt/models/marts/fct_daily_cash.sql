with opening as (
    select
        scenario_id,
        account_id,
        currency,
        opening_cash
    from {{ ref('stg_activity_events') }}
    where record_type = 'OPENING_CASH'
),

sessions as (
    select
        scenario_id,
        business_date,
        cutoff
    from {{ ref('stg_activity_events') }}
    where record_type = 'SESSION'
),

totals as (
    select
        scenario_id,
        business_date,
        account_id,
        currency,
        sum(coalesce(confirmed_cash, 0)) as confirmed_cash_change,
        sum(case when outstanding_cash > 0 then outstanding_cash else 0 end) as receivables,
        -sum(case when outstanding_cash < 0 then outstanding_cash else 0 end) as payables,
        sum(expected_cash) as trade_cash_change,
        count_if(settlement_status = 'NO_CONFIRMATION') as unconfirmed_due_trades
    from {{ ref('fct_settlement_obligations') }}
    group by scenario_id, business_date, account_id, currency
),

dividends as (
    select
        s.scenario_id,
        s.business_date,
        a.account_id,
        a.currency,
        sum(case when p.settled_at <= s.cutoff and p.published_at <= s.cutoff
                 then p.cash_amount else 0 end) as confirmed_dividend_cash,
        sum(a.dividend_receivable) as expected_dividend_receivable,
        sum(a.short_dividend_payable) as expected_short_dividend_payable
    from sessions s
    join {{ ref('fct_dividend_accruals') }} a
        on s.scenario_id = a.scenario_id and s.business_date >= a.accrual_date
    left join {{ ref('stg_activity_events') }} p
        on p.record_type = 'DIVIDEND_PAYMENT'
        and p.scenario_id = a.scenario_id and p.account_id = a.account_id
        and p.corporate_action_id = a.event_id and p.currency = a.currency
        and p.instrument_id = a.instrument_id
        and p.cash_amount = a.expected_gross_amount
    group by s.scenario_id, s.business_date, a.account_id, a.currency
),

administrator as (
    select
        s.scenario_id,
        s.business_date,
        e.account_id,
        e.currency,
        sum(case when e.event_type like 'INVESTOR_%' and e.event_date <= s.business_date
                 then e.amount else 0 end) as investor_flows,
        sum(case when e.event_type = 'EXPENSE' and e.payment_date <= s.business_date
                 then e.amount else 0 end) as paid_expenses,
        sum(case when e.event_type = 'EXPENSE' and e.event_date <= s.business_date
                      and e.payment_date > s.business_date then e.amount else 0 end) as expense_payable,
        sum(case when e.event_type = 'EXPENSE' and e.event_date <= s.business_date
                 then e.amount else 0 end) as accrued_expenses
    from sessions s
    join {{ ref('stg_fund_admin_events') }} e on s.scenario_id = e.scenario_id
    group by s.scenario_id, s.business_date, e.account_id, e.currency
)
select
    s.business_date,
    o.*,
    o.opening_cash + coalesce(t.confirmed_cash_change, 0)
        + coalesce(d.confirmed_dividend_cash, 0)
        + coalesce(a.investor_flows, 0) - coalesce(a.paid_expenses, 0) as reported_settled_cash,
    coalesce(d.confirmed_dividend_cash, 0) as confirmed_dividend_cash,
    coalesce(d.expected_dividend_receivable, 0)
        - greatest(coalesce(d.confirmed_dividend_cash, 0), 0) as dividend_receivable,
    coalesce(d.expected_short_dividend_payable, 0)
        - greatest(-coalesce(d.confirmed_dividend_cash, 0), 0) as short_dividend_payable,
    coalesce(t.receivables, 0) as receivables,
    coalesce(t.payables, 0) as payables,
    o.opening_cash + coalesce(t.trade_cash_change, 0) as trade_date_cash,
    coalesce(a.investor_flows, 0) as investor_flows,
    coalesce(a.paid_expenses, 0) as paid_expenses,
    coalesce(a.expense_payable, 0) as expense_payable,
    o.opening_cash + coalesce(t.trade_cash_change, 0) + coalesce(a.investor_flows, 0)
        - coalesce(a.accrued_expenses, 0) as accrual_basis_cash,
    coalesce(t.unconfirmed_due_trades, 0) as unconfirmed_due_trades
from sessions s join opening o on s.scenario_id = o.scenario_id
left join totals t on s.scenario_id = t.scenario_id and s.business_date = t.business_date
    and o.account_id = t.account_id and o.currency = t.currency

left join dividends d on s.scenario_id = d.scenario_id and s.business_date = d.business_date
    and o.account_id = d.account_id and o.currency = d.currency
left join administrator a on s.scenario_id = a.scenario_id and s.business_date = a.business_date
    and o.account_id = a.account_id and o.currency = a.currency
