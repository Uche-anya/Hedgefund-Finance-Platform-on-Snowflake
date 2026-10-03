{{ config(tags=['fixture']) }}
select *
from {{ ref('fct_bank_cash_reconciliation') }}
where (account_id = 'SIM-REPLAY-01' and reconciliation_status <> 'MATCHED')
   or (account_id = 'SIM-REPLAY-02' and
       (reconciliation_status <> 'BALANCE_MISMATCH' or balance_difference <> 25))
   or account_id not in ('SIM-REPLAY-01', 'SIM-REPLAY-02')
qualify count(*) over () <> 2
    or (account_id = 'SIM-REPLAY-01' and reconciliation_status <> 'MATCHED')
    or (account_id = 'SIM-REPLAY-02' and
        (reconciliation_status <> 'BALANCE_MISMATCH' or balance_difference <> 25))
    or account_id not in ('SIM-REPLAY-01', 'SIM-REPLAY-02')
