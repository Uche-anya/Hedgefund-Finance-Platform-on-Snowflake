-- Catch missing, extra or multiplied holdings after the price join.
with valued as (
    select
        valuation_date,
        portfolio,
        instrument,
        count(*) as row_count,
        sum(quantity) as quantity
    from {{ ref('portfolio_valuation') }}
    group by valuation_date, portfolio, instrument
)
select
    h.business_date,
    h.portfolio,
    h.instrument,
    v.valuation_date, v.row_count, v.quantity as valued_quantity
from {{ ref('portfolio_holdings') }} h
full outer join valued v
    on h.business_date = v.valuation_date
    and h.portfolio = v.portfolio
    and h.instrument = v.instrument
where h.instrument is null

      or v.instrument is null

      or v.row_count <> 1

      or v.quantity is null

      or v.quantity <> h.quantity
