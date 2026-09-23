select * from {{ ref('stg_historical_prices') }}
where valuation_date_raw <> to_char(valuation_date, 'YYYY-MM-DD')
   or trim(universe_ticker) = ''
   or trim(source_ticker) = ''
   or low_price <= 0
   or open_price < low_price or open_price > high_price
   or close_price < low_price or close_price > high_price
   or volume < 0
   or input_row_number <= 0 or source_row_number <= 0
   or trim(input_file) = '' or trim(source_file) = ''
   or (identity_status = 'reviewed_ticker_transition'
       and (nullif(trim(instrument_id), '') is null
            or nullif(trim(share_class_figi), '') is null))
