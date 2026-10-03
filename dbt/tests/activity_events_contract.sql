select *
from {{ ref('stg_activity_events') }}
where coalesce(trim(scenario_id), '') = ''

      or coalesce(record_type, '') not in ('EXECUTION', 'SETTLEMENT', 'SESSION', 'OPENING_CASH', 'DIVIDEND_PAYMENT')

      or (record_type in ('EXECUTION', 'SETTLEMENT') and (
       coalesce(trim(event_id), '') = ''
          or coalesce(trim(execution_id), '') = ''

          or coalesce(trim(account_id), '') = ''
          or coalesce(trim(instrument_id), '') = ''

          or coalesce(currency, '') <> 'USD'
          or coalesce(side, '') not in ('BUY', 'SELL')

          or quantity is null
          or quantity <= 0
          or published_at is null))

      or (record_type = 'EXECUTION' and (
       coalesce(trim(source_system), '') = ''
          or business_date is null

          or settlement_due is null
          or settlement_due <= business_date

          or reference_date is null
          or reference_date >= business_date

          or execution_price is null
          or execution_price <= 0

          or coalesce(trim(market_ticker), '') = ''))

      or (record_type = 'SETTLEMENT' and (
       coalesce(trim(source_system), '') = ''
          or settled_at is null

          or published_at < settled_at
          or cash_amount is null

          or (side = 'BUY' and cash_amount >= 0)
          or (side = 'SELL' and cash_amount <= 0)))

      or (record_type = 'SESSION' and (business_date is null
      or cutoff is null

          or business_date <> to_date(convert_timezone('UTC', cutoff))))

      or (record_type = 'OPENING_CASH' and (opening_cash is null
      or opening_cash <= 0

          or coalesce(trim(account_id), '') = ''
          or coalesce(currency, '') <> 'USD'))
