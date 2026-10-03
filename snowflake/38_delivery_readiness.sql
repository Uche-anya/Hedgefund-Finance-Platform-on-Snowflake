-- One receipt per immutable source delivery. A daily run may start only when
-- every pinned delivery is present and its Snowflake row count matches its manifest.
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

CREATE TABLE IF NOT EXISTS NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES (
    source_name VARCHAR NOT NULL,
    delivery_id VARCHAR NOT NULL,
    manifest_sha256 VARCHAR NOT NULL,
    expected_rows NUMBER(38, 0) NOT NULL,
    received_rows NUMBER(38, 0) NOT NULL,
    delivery_status VARCHAR NOT NULL,
    first_loaded_at TIMESTAMP_LTZ,
    last_loaded_at TIMESTAMP_LTZ,
    registered_at TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP() NOT NULL,
    registered_by VARCHAR DEFAULT CURRENT_USER() NOT NULL
);

-- Backfill the eight deliveries already used by the controlled February close.
INSERT INTO NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
    (source_name, delivery_id, manifest_sha256, expected_rows, received_rows,
     delivery_status, first_loaded_at, last_loaded_at)
WITH measured AS (
    SELECT 'activity_events' AS source_name,
        'sim-dividend-a48996d29c0473a090db3b9f' AS delivery_id,
        'a87de8383ec044ff8a44b3acb147c6a677e5d4610b5ec217b820683abbf5abe0' AS manifest_sha256,
        6394 AS expected_rows, COUNT(*) AS received_rows,
        MIN(loaded_at) AS first_loaded_at, MAX(loaded_at) AS last_loaded_at
    FROM NORTHBRIDGE_DEV.RAW.REPLAY_INPUTS
    WHERE delivery_id = 'sim-dividend-a48996d29c0473a090db3b9f'
    UNION ALL
    SELECT 'historical_prices', 'fb25ddd9838840488e4c8b971ff7e0ae',
        'd2c9419364c98830ca171319a2da417fceb907da3347cb5abe7187be5a10a0bb', 250036,
        COUNT(*), MIN(loaded_at), MAX(loaded_at)
    FROM NORTHBRIDGE_DEV.RAW.HISTORICAL_PRICES
    WHERE delivery_id = 'fb25ddd9838840488e4c8b971ff7e0ae'
    UNION ALL
    SELECT 'corporate_actions', '890be0cfdcf2151ebb4aab47f0d53cd9',
        'bd4f4294b9d135245ad48b22fef4f681eb163a523f45256f45f5e41e0e21edff', 3317,
        COUNT(*), MIN(loaded_at), MAX(loaded_at)
    FROM (
        SELECT loaded_at FROM NORTHBRIDGE_DEV.RAW.CORPORATE_ACTIONS
        WHERE load_id = '890be0cfdcf2151ebb4aab47f0d53cd9'
        UNION ALL
        SELECT loaded_at FROM NORTHBRIDGE_DEV.RAW.CORPORATE_ACTION_REVIEWS
        WHERE load_id = '890be0cfdcf2151ebb4aab47f0d53cd9'
    )
    UNION ALL
    SELECT 'broker_positions', 'sim-broker-42a53a52c3913f138bf0ba35',
        'e59ce2f59975b207ecc559aa4b7d4df85ef74a9af73e955af044bd3bed193cc2', 40,
        COUNT(*), MIN(loaded_at), MAX(loaded_at)
    FROM NORTHBRIDGE_DEV.RAW.BROKER_POSITIONS
    WHERE delivery_id = 'sim-broker-42a53a52c3913f138bf0ba35'
    UNION ALL
    SELECT 'fx_rates', 'fx_rates-43dbf8fe9f4939cfee844e4f',
        '6c0487de86f44299f03d2e7caa637d1ec294bec1f80cadb9cb4c32a1b62d74e5', 23,
        COUNT(*), MIN(loaded_at), MAX(loaded_at)
    FROM NORTHBRIDGE_DEV.RAW.FX_RATES
    WHERE delivery_id = 'fx_rates-43dbf8fe9f4939cfee844e4f'
    UNION ALL
    SELECT 'treasury_rates', 'treasury_rates-fb72a525531b06c98f3b9cb0',
        '63adf3e0509ce21c4399ded54e3eb0c32acf15d8af90c4c2f707596ed8bb0e1e', 23,
        COUNT(*), MIN(loaded_at), MAX(loaded_at)
    FROM NORTHBRIDGE_DEV.RAW.TREASURY_RATES
    WHERE delivery_id = 'treasury_rates-fb72a525531b06c98f3b9cb0'
    UNION ALL
    SELECT 'fund_admin', 'sim-admin-d4c87abd5740695f47b0bd8c',
        '8fa448d1e08ec649115c559df2dd044b2868230087bc4facc19547b039444a5d', 4,
        COUNT(*), MIN(loaded_at), MAX(loaded_at)
    FROM NORTHBRIDGE_DEV.RAW.FUND_ADMIN_EVENTS
    WHERE delivery_id = 'sim-admin-d4c87abd5740695f47b0bd8c'
    UNION ALL
    SELECT 'bank_cash', 'sim-bank-8690941c886b2dc3602d214f',
        '4bf526c64c1c8d59c3437322919b4d8bf21167c9a851d876f84908097a535ba7', 2,
        COUNT(*), MIN(loaded_at), MAX(loaded_at)
    FROM NORTHBRIDGE_DEV.RAW.BANK_CASH_STATEMENTS
    WHERE delivery_id = 'sim-bank-8690941c886b2dc3602d214f'
)
SELECT source_name, delivery_id, manifest_sha256, expected_rows, received_rows,
       IFF(received_rows = expected_rows, 'READY', 'ROW_COUNT_MISMATCH'),
       first_loaded_at, last_loaded_at
FROM measured m
WHERE NOT EXISTS (
    SELECT 1 FROM NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES d
    WHERE d.source_name = m.source_name AND d.delivery_id = m.delivery_id
);

CREATE OR REPLACE VIEW NORTHBRIDGE_DEV.OPERATIONS.DELIVERY_EXCEPTIONS AS
SELECT *
FROM NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
WHERE delivery_status <> 'READY' OR received_rows <> expected_rows;

USE ROLE SECURITYADMIN;
GRANT USAGE ON SCHEMA NORTHBRIDGE_DEV.OPERATIONS TO ROLE NORTHBRIDGE_DBT_DEV;
GRANT SELECT ON TABLE NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES TO ROLE NORTHBRIDGE_DBT_DEV;
GRANT SELECT ON VIEW NORTHBRIDGE_DEV.OPERATIONS.DELIVERY_EXCEPTIONS TO ROLE NORTHBRIDGE_DBT_DEV;
GRANT USAGE ON SCHEMA NORTHBRIDGE_DEV.OPERATIONS TO ROLE NORTHBRIDGE_INGEST;
GRANT SELECT, INSERT ON TABLE NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES TO ROLE NORTHBRIDGE_INGEST;
GRANT SELECT ON TABLE NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES TO ROLE NORTHBRIDGE_RUNNER;

USE ROLE SYSADMIN;
SELECT source_name, delivery_id, expected_rows, received_rows, delivery_status
FROM NORTHBRIDGE_DEV.OPERATIONS.DELIVERIES
ORDER BY source_name;
