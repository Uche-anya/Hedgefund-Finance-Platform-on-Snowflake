select *
from {{ ref('stg_corporate_actions') }}
where coalesce(trim(ticker), '') = ''

      or action_type not in ('splits', 'dividends')
      or action_type is null

      or snapshot_id is null
      or source_file is null
      or source_row_number is null

      or coalesce(array_size(source_event_ids), 0) = 0

      or (action_type = 'dividends' and (ex_dividend_date is null
      or pay_date is null

          or record_date is null
          or coalesce(currency, '') <> 'USD'

          or cash_amount is null
          or cash_amount <= 0))

      or (action_type = 'splits' and (execution_date is null

          or split_from is null
          or split_from <= 0
          or split_to is null
          or split_to <= 0))
