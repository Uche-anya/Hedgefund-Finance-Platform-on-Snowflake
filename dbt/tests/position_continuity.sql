with compared as (
    select
        *,
        lag(closing_quantity, 1, 0) over (
        partition by scenario_id, account_id, instrument_id order by business_date) as previous_close
    from {{ ref('fct_daily_positions') }}
)
select *
from compared
where opening_quantity is null
   or closing_quantity is null
   or net_trade_quantity is null

      or opening_quantity <> previous_close

      or closing_quantity <> opening_quantity + net_trade_quantity
