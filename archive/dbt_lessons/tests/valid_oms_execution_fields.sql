select *
from {{ ref('stg_oms_executions') }}
where quantity <= 0

      or execution_price <= 0

      or settlement_due < business_date

      or published_at < executed_at

      or business_date_raw <> to_char(business_date, 'YYYY-MM-DD')

      or settlement_due_raw <> to_char(settlement_due, 'YYYY-MM-DD')

      or coalesce(trim(event_id), '') = ''

      or coalesce(trim(execution_id), '') = ''

      or coalesce(trim(order_id), '') = ''

      or coalesce(trim(fund_id), '') = ''

      or coalesce(trim(account_id), '') = ''

      or coalesce(trim(broker_id), '') = ''

      or coalesce(trim(instrument_id), '') = ''

      or coalesce(trim(market_ticker), '') = ''

      or coalesce(source_system, '') <> 'simulated_oms'

      or coalesce(message_source_system, '') <> source_system

      or coalesce(message_scenario_id, '') <> scenario_id

      or coalesce(trim(scenario_id), '') = ''

      or coalesce(trim(source_file), '') = ''

      or source_row_number is null

      or source_row_number < 1

      or loaded_at is null
