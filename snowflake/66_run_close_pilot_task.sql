-- Start the suspended root once. Its resumed child builds the pinned dbt close.
USE ROLE SYSADMIN;
EXECUTE TASK NORTHBRIDGE_DEV.OPERATIONS.CLOSE_PILOT_GATE
    USING CONFIG = $${"request_id": "5d1f1abedf4cbe14e6a6cef3", "supersedes_request_id": "61c294231f2d4a5b5512e9c8"}$$;
