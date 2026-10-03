-- Run this manually only after reviewing the candidate and reconciliation results.
USE ROLE NORTHBRIDGE_NAV_REVIEWER;

SELECT *
FROM NORTHBRIDGE_DEV.OPERATIONS.NAV_REVIEW_CANDIDATES
WHERE business_date = '2025-02-07'
  AND scenario_id = 'sim-replay-406bbef8179cdbb0a3dd6df3';

SELECT *
FROM NORTHBRIDGE_DEV.OPERATIONS.BROKER_RECONCILIATION_SUMMARY
WHERE statement_date = '2025-01-30';
-- This fixture currently has its independent broker statement at 2025-01-30.
-- Production would normally wait for the statement covering the close date.

-- Uncomment only after the two queries above have been reviewed.
-- INSERT INTO NORTHBRIDGE_DEV.OPERATIONS.NAV_APPROVALS
--     (approval_id, business_date, scenario_id, candidate_hash, decision, review_note)
-- SELECT UUID_STRING(), business_date, scenario_id, candidate_hash, 'APPROVED',
--        'Reviewed NAV, source readiness, dbt tests and reconciliation exceptions.'
-- FROM NORTHBRIDGE_DEV.OPERATIONS.NAV_REVIEW_CANDIDATES
-- WHERE business_date = '2025-02-07'
--   AND scenario_id = 'sim-replay-406bbef8179cdbb0a3dd6df3';
