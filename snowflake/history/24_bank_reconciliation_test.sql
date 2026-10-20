USE ROLE SYSADMIN;

BEGIN TRANSACTION;
UPDATE NORTHBRIDGE_TEST.RAW.DAILY_BANK_STATEMENTS
SET payload = OBJECT_INSERT(payload, 'closing_balance', '4994888.66', TRUE)
WHERE payload:statement_date::varchar = '2026-10-16'
  AND payload:account_id::varchar = 'SIM-ACCOUNT-01';

SELECT account_id, difference_usd, reconciliation_status
FROM NORTHBRIDGE_TEST.DBT_TEST.FCT_CASH_RECONCILIATION
WHERE statement_date = '2026-10-16' AND account_id = 'SIM-ACCOUNT-01';
ROLLBACK;

BEGIN TRANSACTION;
DELETE FROM NORTHBRIDGE_TEST.RAW.DAILY_BANK_STATEMENTS
WHERE payload:statement_date::varchar = '2026-10-16'
  AND payload:account_id::varchar = 'SIM-ACCOUNT-02';

SELECT account_id, reconciliation_status
FROM NORTHBRIDGE_TEST.DBT_TEST.FCT_CASH_RECONCILIATION
WHERE statement_date = '2026-10-16' AND account_id = 'SIM-ACCOUNT-02';
ROLLBACK;
