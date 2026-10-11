"""Choose the US market date for an overnight producer run."""

from datetime import datetime, timedelta, timezone
import sys
from zoneinfo import ZoneInfo

from pipeline.us_equity_calendar import is_market_day


NEW_YORK = ZoneInfo("America/New_York")


def scheduled_close(now):
    day = now.astimezone(NEW_YORK).date() - timedelta(days=1)
    if is_market_day(day):
        return day
    return None


def main():
    day = scheduled_close(datetime.now(timezone.utc))
    if day is None:
        print("run=false")
        print("No US equity close yesterday; nothing to deliver", file=sys.stderr)
    else:
        print("run=true")
        print("business_date={}".format(day.isoformat()))


if __name__ == "__main__":
    main()
