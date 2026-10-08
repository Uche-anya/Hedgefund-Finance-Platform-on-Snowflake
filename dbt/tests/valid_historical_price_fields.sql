select *
from {{ ref('stg_historical_prices') }}
where valuation_date is null

      or valuation_date_raw <> to_char(valuation_date, 'YYYY-MM-DD')

      or open_price is null
      or high_price is null
      or low_price is null

      or close_price is null
      or volume is null

      or input_row_number is null
      or source_row_number is null
      or loaded_at is null

      or coalesce(currency, '') <> 'USD'

      or coalesce(price_basis, '') <> 'unadjusted'

      or coalesce(source_system, '') not in (
          'massive'
          {% if target.name == 'dev' %}, 'simulated_price_correction'{% endif %}
      )

      or coalesce(identity_status, '') not in ('reviewed_ticker_transition', 'provider_ticker_only')

      or coalesce(trim(universe_ticker), '') = ''

      or coalesce(trim(source_ticker), '') = ''

      or low_price <= 0

      or open_price < low_price
      or open_price > high_price

      or close_price < low_price
      or close_price > high_price

      or volume < 0

      or input_row_number <= 0
      or source_row_number <= 0

      or coalesce(trim(input_file), '') = ''
      or coalesce(trim(source_file), '') = ''

      or (identity_status = 'reviewed_ticker_transition'
       and (nullif(trim(instrument_id), '') is null

               or nullif(trim(share_class_figi), '') is null))
