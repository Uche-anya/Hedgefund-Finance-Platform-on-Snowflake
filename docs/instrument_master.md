# Instrument master

The replay uses 20 ticker symbols, but a ticker is only a market label. It can be
renamed, reused or kept while the listed security changes. `dbt/seeds/dim_instrument.csv`
gives each reviewed security a Northbridge ID and dates the external identifiers.

## XOM transition

Exxon Mobil Corporation used `NB_EQ_0015` through 1 July 2026. The new holding
company uses `NB_EQ_0021` from 2 July 2026. Both traded as XOM, but Massive
reported different share-class FIGIs. The SEC filings describe a one-for-one
holding-company reorganisation and trading in the new shares from 2 July.

Massive returned the old issuer CIK for its 2 July reference record. The seed
therefore keeps that value in `provider_cik` and records the reviewed successor
CIK separately in `reviewed_issuer_cik`. Raw provider evidence is never rewritten.

## Join rule

Trades, prices and corporate actions match the dimension with:

```text
ticker = ticker
and event date between valid_from and valid_to
```

Downstream positions and valuations use `security_id`. Tests reject incomplete
reference rows, duplicate identifiers, overlapping date ranges, unmapped replay
trades and prices that map to zero or multiple securities.
