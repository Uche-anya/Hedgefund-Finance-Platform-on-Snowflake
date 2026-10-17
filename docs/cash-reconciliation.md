# Daily bank cash check

The bank feed is fictional. It travels through a separate delivery from the
fund's cash calculation, but both still start with our simulated trades. A
match does not count as confirmation from a real bank.

For each account, the new bank file contains an opening balance, individual
dated postings, and a closing balance. The next market day starts with the
previous bank statement's closing balance. The producer waits for the day's
OMS delivery and for the previous close to be validated. It stops if a booked
dividend reaches its pay date: we do not yet have bank payment evidence.

The loader checks that opening balance plus postings equals closing balance,
then saves an immutable JSONL delivery in `RAW.DAILY_BANK_STATEMENTS`.
`FCT_CASH_RECONCILIATION` also checks the roll-forward in Snowflake and
checks that today's bank opening equals the prior bank close. Finally it
compares bank cash with `FCT_CASH_DAILY`. The close task records
`VALIDATED` only when both accounts have `MATCH`.

The October 16 dry run reproduced the two existing balances:
$4,994,888.65 and $4,978,139.30. The October 16 statement already loaded
is a balance-only legacy delivery; its validated close is unchanged. The new
ledger format applies to future deliveries.

Run `snowflake/25_bank_ledger_test.sql` in TEST to see a $50 bank fee produce
`BREAK`. The script then adds a bank reversal, which returns the comparison
to `MATCH`, and rolls the whole exercise back. This illustrates a **bank
error** corrected by the bank. A genuine fee would remain a break until an
approved fund expense was booked and NAV recalculated. The project does not
yet contain that expense workflow or an operator review log.

Daily production would use bank-supplied transactions and statements in place
of this simulator. The delivery and reconciliation contract can stay the same.
