select *
from {{ ref('fct_position_daily') }}
where market_value <> shares * close_price
