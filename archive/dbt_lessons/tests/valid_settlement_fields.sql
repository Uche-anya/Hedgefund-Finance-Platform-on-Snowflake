select *
from {{ ref('stg_settlements') }}
where coalesce(event_type, '') <> 'SETTLEMENT_CONFIRMED'

      or coalesce(settlement_status, '') <> 'SETTLED'

      or coalesce(source_system, '') <> 'simulated_custodian'

      or coalesce(is_simulated, '') <> 'true'

      or coalesce(schema_version, '') <> '1'

      or coalesce(currency, '') <> 'USD'

      or coalesce(side, '') not in ('BUY', 'SELL')

      or settled_quantity <= 0

      or (side = 'BUY' and cash_amount >= 0)

      or (side = 'SELL' and cash_amount <= 0)

      or published_at < settled_at

      or settlement_date_raw <> to_char(settlement_date, 'YYYY-MM-DD')

      or settlement_date <> to_date(convert_timezone('UTC', settled_at))

      or coalesce(trim(event_id), '') = ''

      or coalesce(trim(settlement_id), '') = ''

      or coalesce(trim(execution_id), '') = ''

      or coalesce(trim(scenario_id), '') = ''

      or coalesce(trim(fund_id), '') = ''

      or coalesce(trim(account_id), '') = ''

      or coalesce(trim(broker_id), '') = ''

      or coalesce(trim(instrument_id), '') = ''

      or coalesce(trim(source_file), '') = ''

      or source_row_number is null
      or source_row_number < 1
      or loaded_at is null
