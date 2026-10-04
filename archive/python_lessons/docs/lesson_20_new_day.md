# Part 20: process a genuinely new day

Run 10 January using the published 9 January close:

```powershell
python -m fund_pipeline.run_daily --config configs/daily_usd_2025-01-10.json
```

All new activity, prices and comparison statements in this lesson are simulated.
The input fixtures are in the three `fixtures/daily_*/2025-01-10/` folders.
The configuration selects preserved deliveries from those fixtures, the published
opening in `data/daily_usd_demo.sqlite`, and the candidate destination in
`data/daily_usd_pipeline.sqlite`. A fresh checkout needs its own saved opening
and landed deliveries before using this machine's example configuration.

## What changed overnight?

| Item | 9 January close | 10 January close |
| --- | ---: | ---: |
| Apple quantity | 13 | 13 |
| Amazon quantity | -3 | -3 |
| Apple closing price, USD | 245.00 | 250.00 |
| Amazon closing price, USD | 225.00 | 225.00 |
| Cash, USD | 8,248.05 | 7,528.05 |
| Payable, USD | 720.00 | 0.00 |
| NAV, USD | 10,038.05 | 10,103.05 |

There are no new trades. Execution, allocation and execution-term files contain
headers only: an explicit empty batch. Holdings carry forward unchanged.

The settlement file confirms payment of the old Apple purchase, SIM-D2-E001.
Cash falls by USD 720 and that payable disappears. The comparison statement of
open obligations also has headers only because nothing remains unpaid.

Apple's invented closing price rises by USD 5. We own 13 shares, so the gain is
13 times 5 = USD 65. Amazon's price does not move.

    NAV = 7,528.05 cash + 13*250 Apple - 3*225 Amazon - 0 payable
        = USD 10,103.05

The USD 720 payment itself does not reduce NAV: cash and debt fall together.

## Inspect the saved result

```powershell
python -m fund_pipeline.publication --database data/daily_usd_pipeline.sqlite show --candidate 8b6b95dd57f7487994e23cd588005c3b
```

The demonstration run is `b8ee62d0df4a44ceb02607c25c36270a`, saved under
`data/daily_runs/`. It passed six comparisons: two positions, settled cash, NAV,
total payables and total receivables. There is no individual outstanding obligation
left to compare. All four earlier execution IDs remain recorded.

This is a new valuation date and therefore a new candidate, not a retry of
9 January. Repeating the 10 January command with unchanged inputs and code can
reuse this candidate. It initially reached READY_FOR_REVIEW without approval.

## Completed review and publication

On 20 September 2026, the saved candidate was inspected and approved under
`demo-reviewer` with an explicit local learning-demonstration note. It was then
published as **10 January 2025, version 1** in `data/daily_usd_pipeline.sqlite`.
Reading `current` confirmed USD 7,528.05 cash, zero unpaid obligations, USD 10,103.05
NAV and all four known execution IDs. It can now supply a later daily opening.

```powershell
python -m fund_pipeline.publication --database data/daily_usd_pipeline.sqlite current --as-of 2025-01-10
```
