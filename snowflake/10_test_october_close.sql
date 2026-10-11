-- One manual graph run. The root schedule stays suspended.
-- The two child tasks must be resumed first.
EXECUTE TASK NORTHBRIDGE_DEV.DBT_DEV.DAILY_CLOSE_READY
    USING CONFIG = $${"business_date": "2026-10-09"}$$;
