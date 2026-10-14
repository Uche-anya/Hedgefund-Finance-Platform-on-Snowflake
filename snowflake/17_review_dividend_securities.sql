-- Reviewed against Massive ticker details dated 2026-10-14.
-- MSFT was also checked on its first simulator date, 2026-10-08.
-- The OMS instrument IDs here are our own ticker-based simulator convention.
USE ROLE SYSADMIN;

UPDATE NORTHBRIDGE_DEV.RAW.SECURITY_MAPPINGS m
SET status = 'APPROVED',
    provider_cik = r.cik,
    share_class_figi = r.figi,
    evidence_ref = r.evidence_ref,
    approved_by = CURRENT_USER(),
    approved_at = CURRENT_TIMESTAMP(),
    note = 'Simulated OMS symbol mapped to the dated Massive share class'
FROM (
    SELECT column1 AS instrument_id, column2 AS provider_ticker,
        TO_DATE(column3) AS valid_from, column4 AS cik, column5 AS figi,
        column6 AS evidence_ref
    FROM VALUES
        ('PG.US', 'PG', '2026-10-14', '0000080424', 'BBG001S5V4L9',
         'Massive ticker overview 2026-10-14 request e0a9b95562a0a9ad80fb546d456db39a'),
        ('MSFT.US', 'MSFT', '2026-10-08', '0000789019', 'BBG001S5TD05',
         'Massive ticker overview 2026-10-08 request 0ce96da1642ef67f981ffdeaec171f47; 2026-10-14 request 0b88c0136bb372d6071d7aa53e755267'),
        ('JNJ.US', 'JNJ', '2026-10-14', '0000200406', 'BBG001S5SHQ9',
         'Massive ticker overview 2026-10-14 request 05b09df8d0482fc721cbb0a14ab072ec')
) r
WHERE m.instrument_id = r.instrument_id
  AND m.provider_ticker = r.provider_ticker
  AND m.valid_from = r.valid_from
  AND m.status = 'PENDING';

SELECT instrument_id, provider_ticker, valid_from, status,
    provider_cik, share_class_figi, approved_by, approved_at
FROM NORTHBRIDGE_DEV.RAW.SECURITY_MAPPINGS
WHERE provider_ticker IN ('PG', 'MSFT', 'JNJ')
ORDER BY provider_ticker;
