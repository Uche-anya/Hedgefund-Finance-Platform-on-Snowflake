-- Candidate fund securities. Approval needs current identity evidence.
USE ROLE SYSADMIN;

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.RAW.SECURITY_MAPPINGS (
    instrument_id VARCHAR,
    provider_ticker VARCHAR,
    valid_from DATE,
    valid_to DATE,
    status VARCHAR,
    provider_cik VARCHAR,
    share_class_figi VARCHAR,
    evidence_ref VARCHAR,
    approved_by VARCHAR,
    approved_at TIMESTAMP_LTZ,
    note VARCHAR
);

MERGE INTO NORTHBRIDGE_DEV.RAW.SECURITY_MAPPINGS m
USING (
    SELECT column1 AS instrument_id, column2 AS provider_ticker,
        TO_DATE(column3) AS valid_from
    FROM VALUES
        ('AAPL.US', 'AAPL', '2026-10-08'),
        ('AMZN.US', 'AMZN', '2026-10-08'),
        ('MSFT.US', 'MSFT', '2026-10-08'),
        ('KO.US', 'KO', '2026-10-08'),
        ('GOOGL.US', 'GOOGL', '2026-10-14'),
        ('META.US', 'META', '2026-10-14'),
        ('NVDA.US', 'NVDA', '2026-10-14'),
        ('V.US', 'V', '2026-10-14'),
        ('MA.US', 'MA', '2026-10-14'),
        ('COST.US', 'COST', '2026-10-14'),
        ('HD.US', 'HD', '2026-10-14'),
        ('MCD.US', 'MCD', '2026-10-14'),
        ('JPM.US', 'JPM', '2026-10-14'),
        ('BAC.US', 'BAC', '2026-10-14'),
        ('XOM.US', 'XOM', '2026-10-14'),
        ('JNJ.US', 'JNJ', '2026-10-14'),
        ('PG.US', 'PG', '2026-10-14'),
        ('WMT.US', 'WMT', '2026-10-14'),
        ('PEP.US', 'PEP', '2026-10-14'),
        ('UNH.US', 'UNH', '2026-10-14')
) c
ON m.instrument_id = c.instrument_id AND m.valid_from = c.valid_from
WHEN NOT MATCHED THEN INSERT
    (instrument_id, provider_ticker, valid_from, status, note)
    VALUES (c.instrument_id, c.provider_ticker, c.valid_from,
            'PENDING', 'Check current Massive identity before approval');

USE ROLE SECURITYADMIN;
GRANT SELECT ON TABLE NORTHBRIDGE_DEV.RAW.SECURITY_MAPPINGS
    TO ROLE NORTHBRIDGE_DBT_DEV;
