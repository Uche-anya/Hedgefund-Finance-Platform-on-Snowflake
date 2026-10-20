-- Run in TEST. The bank reports a $50 fee that the fund books do not contain.
-- Rollback leaves the saved TEST statement unchanged.
USE ROLE SYSADMIN;
BEGIN TRANSACTION;

UPDATE NORTHBRIDGE_TEST.RAW.DAILY_BANK_STATEMENTS
SET payload = OBJECT_INSERT(payload, 'previous_statement_date', '2026-10-07', TRUE)
WHERE payload:statement_date::varchar = '2026-10-16'
  AND payload:account_id::varchar = 'SIM-ACCOUNT-01';
UPDATE NORTHBRIDGE_TEST.RAW.DAILY_BANK_STATEMENTS
SET payload = OBJECT_INSERT(payload, 'opening_balance', '5000000.00', TRUE)
WHERE payload:statement_date::varchar = '2026-10-16'
  AND payload:account_id::varchar = 'SIM-ACCOUNT-01';
UPDATE NORTHBRIDGE_TEST.RAW.DAILY_BANK_STATEMENTS
SET payload = OBJECT_INSERT(payload, 'postings', PARSE_JSON(
    '[{"posting_id":"SETTLEMENTS","posting_date":"2026-10-16","amount":"-5111.35","type":"TRADE_SETTLEMENT"},'
    || '{"posting_id":"BANK-FEE-1","posting_date":"2026-10-16","amount":"-50.00","type":"BANK_FEE"}]'), TRUE)
WHERE payload:statement_date::varchar = '2026-10-16'
  AND payload:account_id::varchar = 'SIM-ACCOUNT-01';
UPDATE NORTHBRIDGE_TEST.RAW.DAILY_BANK_STATEMENTS
SET payload = OBJECT_INSERT(payload, 'closing_balance', '4994838.65', TRUE)
WHERE payload:statement_date::varchar = '2026-10-16'
  AND payload:account_id::varchar = 'SIM-ACCOUNT-01';

-- Expected: BREAK, difference_usd = -50.00. Both bank numbers roll forward.
SELECT account_id, bank_opening_cash, posted_cash, bank_cash,
    calculated_cash_balance, difference_usd, reconciliation_status
FROM NORTHBRIDGE_TEST.DBT_TEST.FCT_CASH_RECONCILIATION
WHERE statement_date = '2026-10-16'
  AND account_id = 'SIM-ACCOUNT-01';

-- In this example the fee was a bank error. The bank reverses it.
-- If the fee were genuine, the fund would need an approved expense posting.
UPDATE NORTHBRIDGE_TEST.RAW.DAILY_BANK_STATEMENTS
SET payload = OBJECT_INSERT(payload, 'postings', PARSE_JSON(
    '[{"posting_id":"SETTLEMENTS","posting_date":"2026-10-16","amount":"-5111.35","type":"TRADE_SETTLEMENT"},'
    || '{"posting_id":"BANK-FEE-1","posting_date":"2026-10-16","amount":"-50.00","type":"BANK_FEE"},'
    || '{"posting_id":"BANK-FEE-REVERSAL-1","posting_date":"2026-10-16","amount":"50.00","type":"BANK_FEE_REVERSAL"}]'), TRUE)
WHERE payload:statement_date::varchar = '2026-10-16'
  AND payload:account_id::varchar = 'SIM-ACCOUNT-01';
UPDATE NORTHBRIDGE_TEST.RAW.DAILY_BANK_STATEMENTS
SET payload = OBJECT_INSERT(payload, 'closing_balance', '4994888.65', TRUE)
WHERE payload:statement_date::varchar = '2026-10-16'
  AND payload:account_id::varchar = 'SIM-ACCOUNT-01';

-- Expected: MATCH after the correcting bank transaction.
SELECT account_id, difference_usd, reconciliation_status
FROM NORTHBRIDGE_TEST.DBT_TEST.FCT_CASH_RECONCILIATION
WHERE statement_date = '2026-10-16'
  AND account_id = 'SIM-ACCOUNT-01';
ROLLBACK;

-- Expected: the original MATCH after the test transaction is rolled back.
SELECT account_id, difference_usd, reconciliation_status
FROM NORTHBRIDGE_TEST.DBT_TEST.FCT_CASH_RECONCILIATION
WHERE statement_date = '2026-10-16'
  AND account_id = 'SIM-ACCOUNT-01';
