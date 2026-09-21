# Part 22: a sourced, versioned valuation calendar

We now have a saved calendar for **January 2025 US equity valuation dates**:
`calendars/us_equities_2025_01_v1.json`. Each day is listed once with its open/closed
status and reason. The file records source URLs, review date, coverage and our
project version. It is a manually curated teaching calendar, not a live exchange feed.

## Sources and an important correction

The normal January closures were checked against the
[NYSE Group calendar announcement](https://s2.q4cdn.com/154085107/files/doc_news/NYSE-Group-Announces-2024-2025-and-2026-Holiday-and-Early-Closings-Calendar-2023.pdf).
Nasdaq separately confirms [20 January's MLK holiday](https://nasdaqtrader.com/TraderNews.aspx?id=ETA2025-4)
and the [exceptional 9 January closure](https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2025-1)
for President Carter's national day of mourning. Other January weekdays are
listed as open under the regular weekday schedule; weekends are closed.

Our earlier 9 January trades and prices were invented teaching fixtures. That
date was not a real US equity trading session. Those saved examples remain under
their original weekday-only policy; the new calendar correctly rejects 9 January
as an opening or valuation date. We do not rewrite historical publications or
claim that their entire simulated history now follows a real exchange calendar.

## What the calendar changes

    Friday 17 January -> Tuesday 21 January
    Wednesday 8 January -> Friday 10 January

The first skips the weekend and the MLK holiday. The second skips the exceptional
closure. Both selected endpoints must be open. You cannot skip a required open day
because its data is missing. The calendar validates the explicitly selected opening;
it does not automatically find or publish missing opening balances.

Coverage is limited to 1-31 January 2025. Dates outside that range fail rather
than falling back to a weekday guess. The file must contain every date in order;
missing, duplicate or malformed rows are rejected.

## Run with the calendar

```powershell
python run_daily.py --config configs/daily_usd_2025-01-13_exchange_calendar.json
```

This opt-in example uses the existing published Friday 10 January opening and
simulated Monday inputs. It still calculates USD 10,103.05 NAV. The six controls
pass, and the result is saved for review without approval or publication.

The configuration adds two fields:

```json
"calendar": "../calendars/us_equities_2025_01_v1.json",
"calendar_sha256": "the exact fingerprint of that file"
```

The supplied configuration already has the full correct fingerprint. Relative
paths are resolved from the configuration folder. Both fields must be supplied
together. Old configurations without them retain the explicitly recorded
WEEKDAYS_ONLY_NO_HOLIDAYS policy for compatibility with earlier lessons.

## Why record a version and fingerprint?

The version (`project-v1`) is our label, not an exchange-issued version number.
The fingerprint checks exact bytes. Editing the calendar without updating the
selected fingerprint stops the run. For a reviewed correction, save a new calendar
file/version and explicitly select it in a new configuration.

Every calendar-aware candidate stores a complete snapshot with source URLs, date
coverage, version and fingerprint. Its reuse key includes that fingerprint, so
selecting a changed calendar creates a new candidate. Previous candidates retain
their original calendar. The runner reads a snapshot once for the calculation;
it does not repeatedly consult a changing online calendar.

The source URLs establish provenance, not an automated authenticity check. This
version was reviewed in September 2026 for historical lessons; it is not a claim
that our system downloaded or knew the calendar at the time of the 2025 run.

## Valuation dates and payment dates are separate

Closing the equity market does not itself move cash or settle a trade. We still
require an actual confirmation for an open obligation, with its date after the
opening close and through the new close. A supplied payment on a market-closed
date can therefore be processed in the next valuation batch. Tests demonstrate
this distinction; they do not assert that a particular bank or clearing system
would settle that payment on that date.

Without confirmation, the obligation remains unpaid. Due dates are not shifted
by this valuation calendar. Provider-specific settlement calendars, partial
settlement, late corrections, time-of-day cutoffs and early-close scheduling are
still future work. We have not added a full-year or multi-exchange calendar.

Missing prices or references on an open day continue to produce failed runs, not
calendar skips. No scheduler or new market-data download is part of this lesson.
