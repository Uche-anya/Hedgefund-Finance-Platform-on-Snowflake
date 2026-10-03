-- A review list at the selected cutoff, not a record of proven payment failures.
select
    scenario_id,
    execution_id,
    account_id,
    instrument_id,
    side,
    expected_quantity,
    settled_quantity,
    expected_currency,
    confirmed_currency,
    expected_cash_change,
    confirmed_cash_change,
    settlement_due,
    reconciliation_status as exception_type,
    case reconciliation_status
        when 'NO_CONFIRMATION' then 'No settlement confirmation received by the report cutoff'
        when 'DETAILS_MISMATCH' then 'Trade and confirmation details disagree'
        when 'UNEXPECTED_CONFIRMATION' then 'Confirmation has no matching trade in this report'
    end as review_reason,
    oms_delivery_id,
    settlement_delivery_id,
    confirmation_event_id,
    confirmation_file,
    as_of
from {{ ref('oms_settlement_reconciliation') }}
where reconciliation_status in ('DETAILS_MISMATCH', 'UNEXPECTED_CONFIRMATION')

      or (
       reconciliation_status = 'NO_CONFIRMATION'
       and settlement_due <= to_date(convert_timezone('UTC', as_of))
   )
