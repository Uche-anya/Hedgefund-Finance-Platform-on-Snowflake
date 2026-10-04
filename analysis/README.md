# Portfolio close analysis

`portfolio_close_analysis.sql` is a read-only analysis pack for the completed
development replay. It uses the existing dbt marts and creates no Snowflake
objects.

`executive_summary.sql` returns the compact account-level measures used in
[`docs/analysis_findings.md`](../docs/analysis_findings.md).

Run it after a successful dbt build:

```powershell
.\.venv\snowflake-cli\Scripts\python.exe scripts\snow_admin.py --file analysis\portfolio_close_analysis.sql
```

The six result sets answer different questions:

1. **Latest scorecard:** NAV, long exposure, short exposure, gross exposure, net
   exposure, cash and open positions.
2. **Flow-adjusted performance:** daily and cumulative return with investor money
   movements removed, plus drawdown from the previous peak.
3. **Concentration:** each position's share of gross exposure and the account's
   Herfindahl concentration index.
4. **NAV attribution:** price movement, trade execution against the close and a
   visible residual for dividends, expenses and other accounting effects.
5. **Settlement quality:** confirmation rate and overdue cash exposure.
6. **Independent breaks:** broker-position and bank-cash differences requiring
   investigation.

## Why these measures matter

### Gross and net exposure

Gross exposure is long market value plus the absolute value of shorts. It shows
how much market risk is being carried. Net exposure is long value minus short
value. A low net exposure does not mean low risk when both the long and short
books are large, which is why both measures are reported relative to NAV.

### Flow-adjusted return

An investor subscription increases cash and NAV, but the investment manager did
not earn it. Daily return therefore removes the day's external flow:

```text
(closing NAV - prior NAV - investor flow) / prior NAV
```

Expenses remain in performance because they are a cost of operating the fund.

### Drawdown

Drawdown measures the decline from the previous high point of the compounded
return series. It answers how far the account fell before recovering. The replay
is only 23 market days, so this is a control demonstration rather than a stable
estimate of long-term risk.

### Concentration

Gross weight uses absolute market value, so a large short position cannot cancel
a large long position. The Herfindahl index is the sum of squared gross weights.
It approaches 1 when one name dominates and falls as risk is spread more evenly.

### NAV attribution

Price P&L applies today's price change to the shares held at the start of the day.
Execution P&L compares today's trade prices with today's close. The remaining
amount is shown explicitly rather than forced into a false market explanation;
it contains dividends, expenses and other accounting effects.

### Operational materiality

A count of failed settlements can be misleading. One missing million-dollar
payment matters more than ten tiny items. The analysis therefore reports both the
exception rate and the cash exposure. Broker and bank differences remain separate
because a matching internal calculation is not proof that an outside party agrees.

## Limits on interpretation

- Trades and independent statements are simulated, so results demonstrate the
  method rather than manager skill or real operating performance.
- Twenty equities and 23 dates are insufficient for robust volatility, beta,
  Sharpe ratio, factor attribution or machine-learning conclusions.
- ECB translations are reporting views; they are not proof that the fund hedged
  currency exposure.
- The Treasury output is a benchmark estimate, not booked interest income.
