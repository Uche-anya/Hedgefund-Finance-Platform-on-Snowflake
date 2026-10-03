-- Detect missing, extra or multiplied positions after joining prices.
with valued as (
    select
        scenario_id,
        valuation_date,
        fund_id,
        account_id,
        instrument_id,
        count(*) as row_count,
        sum(closing_quantity) as quantity
    from {{ ref('oms_first_day_valuation') }}
    group by scenario_id, valuation_date, fund_id, account_id, instrument_id
)
select
    h.instrument_id,
    v.row_count,
    v.quantity
from {{ ref('oms_first_day_positions') }} h
full outer join valued v
    on h.scenario_id = v.scenario_id
    and h.business_date = v.valuation_date
    and h.fund_id = v.fund_id
    and h.account_id = v.account_id
    and h.instrument_id = v.instrument_id
where h.instrument_id is null

      or v.instrument_id is null

      or v.row_count <> 1

      or v.quantity is null

      or v.quantity <> h.closing_quantity
