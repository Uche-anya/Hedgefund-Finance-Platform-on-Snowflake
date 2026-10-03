select *
from {{ ref('stg_closing_prices') }}
where trim(instrument) = ''

      or close_price <= 0

      or valuation_date_raw <> to_char(valuation_date, 'YYYY-MM-DD')
