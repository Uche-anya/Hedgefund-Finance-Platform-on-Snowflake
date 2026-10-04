# Portfolio close findings

Analysis date: 4 October 2026. The underlying close covers 6 January through
7 February 2025. Queries are in `analysis/portfolio_close_analysis.sql` and
`analysis/executive_summary.sql`.

## Executive reading

Both simulated accounts lost money over the replay after investor cash movements
were removed. Account 02 carried more market risk and experienced the larger
loss and drawdown. Both accounts ended with high cash balances, so the exposure
figures describe relatively low net equity deployment rather than a highly
leveraged fund.

| Measure at 7 February 2025 | Account 01 | Account 02 |
| --- | ---: | ---: |
| NAV | $5,174,264 | $4,813,407 |
| Cumulative flow-adjusted return | -1.44% | -1.80% |
| Gross exposure / NAV | 45.91% | 73.92% |
| Net exposure / NAV | 12.61% | 11.09% |
| Cash / NAV | 84.73% | 93.92% |
| Largest gross position | COST short, 24.21% | META long, 21.21% |
| HHI concentration | 0.110 | 0.116 |
| Overdue settlements | 12 | 20 |
| Overdue cash exposure | $213,738 | $424,884 |

Account 02's gross exposure was about 28 percentage points higher while its net
exposure was slightly lower. The combination indicates a larger matched long and
short book. Net exposure alone would hide that additional risk.

## Performance

The calculation removes a $250,000 subscription from Account 01 on 31 January and
a $100,000 redemption from Account 02 on 3 February. Without this adjustment,
Account 01 would appear to earn a large one-day profit and Account 02 would appear
to suffer a much larger investment loss.

Account 01 reached a flow-adjusted cumulative return of approximately -1.44% and
a maximum drawdown of about -1.51%. Account 02 ended near -1.80% with a maximum
drawdown of about -2.03%. The weakest daily return visible in the replay was about
-0.52% for Account 01 and -1.17% for Account 02, both on 5 February.

These results describe the fictional trading strategy embedded in the simulator.
They do not measure real manager performance.

## Exposure and concentration

Account 01's largest position was a COST short worth about $575,139. Its next
largest positions were AAPL, AMZN, Visa and Goldman Sachs. Account 02 was led by a
$754,533 META long, followed by GS and COST shorts.

HHI values near 0.11 indicate moderate concentration across the 20-name replay.
The largest names still deserve explicit review because a single position
represented more than one fifth of gross exposure in each account.

## P&L explanation

The attribution separates:

- changes in prices applied to opening holdings;
- trade execution prices compared with the same-day close;
- other accounting effects.

Most days reconcile exactly to price and execution P&L. On 4 February the
remaining -$1,500 per account corresponds to the administrator expense, which is
correctly retained as a cost of performance. Small residuals around 10 January
come from the reviewed dividend accounting. Showing these residuals makes the
analysis auditable and prevents expenses or dividends from being mislabeled as
market performance.

## Operational risk

The final close carried 12 overdue confirmations and about $213,738 of related
cash exposure in Account 01. Account 02 carried 20 overdue confirmations and
about $424,884. Account 02 therefore had both the higher investment exposure and
the larger unresolved settlement exposure.

The independent statement controls also found:

- a three-share AMZN broker mismatch for Account 01;
- a missing MSFT broker position for Account 02;
- an unexpected AAPL position in a third broker account;
- a late Account 02 broker statement;
- a $25 bank cash mismatch for Account 02.

The late statement appears once for every position row in the detailed output.
It is one late delivery, not 20 separate late statements. This distinction is
important when producing operational KPIs.

## Decisions a senior analyst would raise

1. Investigate Account 02 first because it combines the larger loss, gross
   exposure, drawdown and overdue-settlement amount.
2. Resolve the missing MSFT record and unexpected third account before accepting
   the broker reconciliation.
3. Confirm whether the $25 bank difference is timing, a fee or a data error; do
   not waive it merely because it is small.
4. Review the COST and META concentrations against an agreed position limit.
5. Treat the 4 February expense residual as explained P&L and retain the source
   administrator event in the close evidence.

## Statistical limits

There are only 22 daily return observations per account after the opening date.
Annualised volatility, Sharpe ratio, beta, VaR and machine-learning results would
look precise but would be unstable. They should be added after the replay covers
at least several months and, for stronger inference, multiple market regimes.
