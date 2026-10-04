# Instrument master

The replay uses 20 ticker symbols, but a ticker is only a market label. It can be
renamed, reused or kept while the listed security changes. `dbt/seeds/dim_instrument.csv`
gives each reviewed security a Northbridge ID and dates the external identifiers.

`security_id` is the stable business key. `instrument_version_id` identifies one
dated row. `is_current` marks the version whose `valid_to` is `9999-12-31`.

## SQ to XYZ

Block kept the same CIK and share-class FIGI when its ticker changed from `SQ`
to `XYZ` on 21 January 2025. Both dimension rows therefore use `NB_EQ_0022`:

| Version | Ticker | Valid from | Valid to | Current |
| --- | --- | --- | --- | --- |
| `NB_EQ_0022_V1` | SQ | 2024-09-23 | 2025-01-20 | false |
| `NB_EQ_0022_V2` | XYZ | 2025-01-21 | 9999-12-31 | true |

That is the Type 2 pattern: close the old row and insert a new version instead
of overwriting the old ticker.

The dates begin at the start of the market-data window used by this project;
they are not the security's original listing dates.

This dimension is a reviewed seed because the identity checks are analyst
evidence, not a dependable daily reference-data feed. If Northbridge later
receives a daily security-master extract, a dbt snapshot or an effective-dated
merge should maintain these versions automatically.

## XOM transition

Exxon Mobil Corporation used `NB_EQ_0015` through 1 July 2026. The new holding
company uses `NB_EQ_0021` from 2 July 2026. Both traded as XOM, but Massive
reported different share-class FIGIs. The SEC filings describe a one-for-one
holding-company reorganisation and trading in the new shares from 2 July.

Massive returned the old issuer CIK for its 2 July reference record. The seed
therefore keeps that value in `provider_cik` and records the reviewed successor
CIK separately in `reviewed_issuer_cik`. Raw provider evidence is never rewritten.

## Join rule

Trades and corporate actions match the dimension with:

```text
ticker = ticker
and event date between valid_from and valid_to
```

Prices use the share-class FIGI and valuation date. Rows where the provider did
not supply a FIGI fall back to the dated ticker. This lets `SQ` prices resolve to
the old Block version and `XYZ` prices resolve to the new version.

Downstream positions and valuations use `security_id`. Tests reject incomplete
reference rows, duplicate version IDs, more than one current version, overlapping
date ranges, unmapped replay trades and mastered prices that map to zero or
multiple versions.
