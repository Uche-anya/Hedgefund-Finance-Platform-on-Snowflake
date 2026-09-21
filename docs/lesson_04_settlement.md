# Part 4: cash paid versus money still owed

A completed trade creates an obligation. Settlement fulfils it by exchanging
cash and securities. Until then, our trade-date positions include the trade,
but settled cash has not moved.

- **Payable:** money we owe for a purchase.
- **Receivable:** money owed to us for a sale.
- **Settled cash:** the cash balance after confirmed payments and receipts.
- **As-of date:** the day whose end-of-day state we are calculating.

## The hand-worked example

Start immediately before the trades with GBP 10,000 cash, no holdings and no
outstanding obligations. Repeat Part 3's three trades with these execution prices:

| Execution | Trade on 14 September | Amount | Due / actual settlement in fixture |
| --- | --- | ---: | --- |
| E001 | Buy 100 ALPHA at GBP 10 | Pay 1,000 | 15 September |
| E002 | Sell 30 ALPHA at GBP 11 | Receive 330 | 16 September |
| E003 | Short 20 BETA at GBP 20 | Receive 400 | 16 September |

These dates and prices are synthetic assumptions, not claims about an exchange's
settlement rules. The quantities still produce 70 ALPHA and -20 BETA shares.
Fees, taxes and borrowing costs are absent from this small example.

| As of end of day | Settled cash | Receivables | Payables | Cash + receivables - payables |
| --- | ---: | ---: | ---: | ---: |
| 14 September | 10,000 | 730 | 1,000 | 9,730 |
| 15 September | 9,000 | 730 | 0 | 9,730 |
| 16 September | 9,730 | 0 | 0 | 9,730 |

The ALPHA trades alone reduce cash by 1,000 - 330 = GBP 670. BETA's short sale
adds GBP 400 when it settles, so the combined net cash change is GBP -270.

The last column stays constant: moving an amount from receivable to cash does
not create income. This subtotal excludes share values, so it is **not NAV**.
Short proceeds also do not establish available buying power; collateral and
restricted cash are not modelled here.

## New input files

The `settlement` bundle contains five files:

| File | One row means |
| --- | --- |
| executions.csv | One executed trade, as in Part 3 |
| allocations.csv | One portfolio's allocation from an execution |
| execution_terms.csv | One execution's currency, price and due date |
| opening_cash.csv | The fund's GBP balance just before this batch's trades |
| settlements.csv | One full-settlement confirmation for an execution |

Keeping terms separate preserves the earlier lesson's execution schema.
`business_date` identifies the 14 September trade batch on every file. Within
settlement records, `settled_on` says when the exchange actually occurred.
A missing confirmation means the amount remains outstanding, even after it is due.

## Run it in PowerShell

```powershell
$settlement = python landing.py --business-date 2026-09-14 --bundle settlement
python cash_settlement.py --business-date 2026-09-14 --as-of 2026-09-14 --delivery "$settlement"
python cash_settlement.py --business-date 2026-09-14 --as-of 2026-09-15 --delivery "$settlement"
python cash_settlement.py --business-date 2026-09-14 --as-of 2026-09-16 --delivery "$settlement"
```

Each command rebuilds from the same original opening cash. It does not take
yesterday's closing cash and apply all trades again.

## Follow the GBP 1,000 purchase through the code

1. `verify_delivery()` checks the saved files against their manifest.
2. `calculate_cash()` calls `build_positions()` so the trade/allocation checks
   still apply. It then reads prices, due dates, confirmations and opening cash.
3. E001's amount is 100 shares times GBP 10 = GBP 1,000. Confirmation S001 must
   match that full amount and currency. Conflicting or additional confirmations fail.
4. For 14 September, S001's actual settlement date is still in the future. The
   code leaves cash unchanged and records a GBP 1,000 payable.
5. For 15 September, S001 is effective. The code subtracts GBP 1,000 from cash
   and adds nothing to payables. It never includes both effects at once.

The cash loop operates once per execution. Splitting a trade across portfolios
does not multiply the fund's payment. Exact repeated execution, allocation and
settlement records also do not multiply its effect.

## Exercise: make the purchase settle late

In the source `fixtures/settlement/2026-09-14/settlements.csv`, change S001's
`settled_on` from `2026-09-15` to `2026-09-17`. Keep its due date unchanged in
`execution_terms.csv`. Save a new delivery and calculate as of 16 September.

Predict the answer first. You should see GBP 10,730 settled cash and GBP 1,000
payable marked OVERDUE. The net cash-and-obligations subtotal remains GBP 9,730.
On 17 September the payable clears and cash becomes GBP 9,730.
Restore the source date to 15 September afterwards; keep saved deliveries unchanged.

## What this does and does not establish

This is a retrospective replay of one trade batch with a complete synthetic
settlement history. It shows economic state on each as-of date. It does not
reconstruct which confirmations were known to an operator at an earlier time.
Source receipt timestamps and incremental updates remain future work.

Unsettled amounts are marked OVERDUE at end of their due date or later.
Partial settlement, cancellation, multiple currencies, additional trading dates,
cost basis, realised P&L and broker reconciliation are not implemented. Cash
totals must be in whole pennies; finer totals fail pending a rounding policy.
Confirmed short proceeds are included once, with no separate double subtraction.

The original Part 1 cash/NAV scenario remains separate. Next, we can bring
trade-derived holdings, this cash/obligations subtotal, and dated closing prices
together into a coherent valuation.
