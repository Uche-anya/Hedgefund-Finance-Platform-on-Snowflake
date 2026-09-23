# Part 9: report dollar balances in pounds

Our US-security example owns and owes amounts in USD. We can express those
amounts in GBP without exchanging any money. That is **reporting-currency
translation**. The USD cash balance, share quantities and trade history remain
unchanged.

## Rate direction: keep the units visible

The European Central Bank (ECB) reports currencies against EUR. To obtain
pounds per dollar we divide its GBP-per-EUR observation by its USD-per-EUR
observation for the same date:

```text
GBP per USD = (GBP per EUR) / (USD per EUR)
GBP amount = USD amount * GBP per USD
```

For a made-up illustration, if EUR 1 = USD 1.25 and EUR 1 = GBP 1.00:

```text
GBP per USD = 1.00 / 1.25 = 0.80
USD 100 * 0.80 = GBP 80
```

Dividing USD 100 by 0.80 would give GBP 125, which uses the rate backwards.
The tests use this independently worked example to catch that mistake.

## Source and valuation convention

**Source: ECB statistics.** We preserve the original daily USD/EUR and GBP/EUR
observations. The GBP-per-USD rate is our derived cross rate, not a separately
published ECB quote. Metadata records that distinction and the formula.

The ECB explains that these are informational reference rates, normally
published around 16:00 CET following an earlier daily determination. This lesson
uses the same-date reference rate with US closing equity prices. It is therefore
not a synchronised US-market-close FX snapshot or an executed FX price.
[ECB reference-rate information](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)

ECB statistics can be reused under its attribution and integrity conditions.
We keep its original response unchanged and label our derived rate as our
calculation. [ECB reuse policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.en.html)
This does not change the restrictions on the EODHD equity-price data or the
private hybrid example. Source documentation was checked on 17 September 2026.

The fixed sample covers 6-8 January 2025. A general trading calendar and a
different production valuation cut-off would require separate design.

## Run it in PowerShell

Download the FX data once:

```powershell
$fx = python -m data_extraction.fx_rates
```

Then use a saved USD NAV delivery from Part 8. For the delivery already created
in this workspace:

```powershell
$navDelivery = 'data/landing/2025-01-06/18ae80085f1043789b5d604ee44dc216'
python -m fund_pipeline.report_gbp --business-date 2025-01-06 --as-of 2025-01-08 --delivery "$navDelivery" --fx-delivery "$fx"
```

If rebuilding from scratch, use `$scenario.nav_delivery` from the Part 8 commands
instead of that existing path. Reuse the `$fx` folder to replay without another
network request. Only `data_extraction/fx_rates.py` needs internet access.

The report prints USD and GBP columns for cash, receivables, payables, long
assets, short obligations and NAV. It saves a JSON snapshot under
`data/reporting/`, with both currencies, the chosen rate, input paths and FX
manifest checksum. The original USD calculation and source files are unchanged.

## Follow a balance through the code

1. `download_fx()` fetches daily USD and GBP observations against EUR and saves
   the original CSV before validation. The shared HTTP helper uses timeouts
   and bounded retries for transient failures.
2. `normalize()` checks daily frequency, EUR denominator, spot reference series,
   units, unique date/currency keys and positive finite values. Both legs must
   exist on every requested sample date.
3. The derived CSV includes the two original legs plus the GBP-per-USD result.
   The cross rate uses 40-digit Decimal working precision, then 12 decimal
   places with ROUND_HALF_UP. A manifest is written last, after success.
4. `verify_fx()` checks fingerprints and rederives the rates from the original
   response. An inverted rate cannot pass just by changing its file checksum.
5. `calculate_gbp()` selects exactly the requested rate date and obtains the
   USD close using our existing trade, settlement and price controls.
6. `translate()` multiplies every monetary component, each position value and
   each outstanding obligation by the same dated rate. Share quantities do
   not change. It checks the sum of converted components equals converted NAV.

```text
GBP NAV = GBP cash + GBP receivables - GBP payables
          + GBP long assets - GBP short obligations
```

The short obligation is subtracted once. Translating it does not create another
liability. Likewise, reporting USD cash in GBP does not record an actual cash
receipt, payment or FX trade.

## Precision and missing data

After the explicit 12-decimal cross-rate boundary, monetary components keep
their Decimal precision. Only displayed amounts round to pennies. Individually
rounded display lines can differ by a penny from their displayed total; the
saved unrounded components explain the difference.

No missing rate is replaced by zero, one, or yesterday's observation. An
incomplete FX download has a failure diagnostic but no ready manifest. The
report refuses missing requested dates, incompatible direction, or changed
raw/derived files. A different date can change GBP NAV even if USD NAV is stable.

## Your exercise

Use the same saved inputs to report 7 January and 8 January. Compare USD NAV
and the GBP-per-USD rate on both dates. Explain why a GBP change cannot be
attributed entirely to share-price changes when the FX rate also changed.
For the simpler isolated-FX example, see the test with constant USD 10,000 and
rates of 0.80 and 0.72: GBP NAV changes from 8,000 to 7,200 with no USD gain/loss.

## Boundary of this lesson

This is a separate **NOT APPROVED** reporting snapshot. Existing reconciliation
and approval/publication still apply to the original single-currency closes.
We have not added an independently prepared GBP administrator comparison or
extended publication candidates to include the FX evidence. Do not treat the
USD approval as approval of this GBP report.

Mixed GBP/USD cash accounts, executed FX trades, realised FX P&L, fee conversion,
weekend fallback policies and historical rate revisions remain future work.
Processing and storage remain local; Snowflake is still disabled.
