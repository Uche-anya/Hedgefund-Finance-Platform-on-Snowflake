-- Run after the October 12 producer has submitted its files and RAW is ready.
-- The root schedule stays suspended; this executes the graph once.
EXECUTE TASK NORTHBRIDGE_DEV.DBT_DEV.DAILY_CLOSE_READY
    USING CONFIG = $${"business_date": "2026-10-12"}$$;
