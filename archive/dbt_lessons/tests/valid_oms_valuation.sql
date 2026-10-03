select *
from {{ ref('oms_first_day_valuation') }}
where close_price <= 0

      or market_value <> closing_quantity * close_price

      or price_basis <> 'unadjusted'

      or price_source_ticker <> market_ticker
