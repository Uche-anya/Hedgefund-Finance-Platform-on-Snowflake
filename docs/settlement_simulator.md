# Settlement confirmations: the next small lesson

Run `python -m simulation.settlement_simulator` from the repository root.
This reads the five saved historical execution messages and verifies their
hashes, trade details and distinct IDs before writing anything.

It creates four JSONL confirmations from a fictional custodian. Each references
the original execution_id and reports full settled quantity and signed cash
amount. Negative cash means paid; positive means received. No fees are modelled.
The January 7 timestamps are fictional historical times, not the script run time.

The Amazon BUY 2 trade has no confirmation at the scenario cutoff of January 7,
2025, 22:00 UTC. Its expected payment is USD 448.52. Missing confirmation does
not prove payment failed: delayed reporting is also possible. We do not assign
a failure cause or emit a fake failed-settlement message.

Confirmed signed cash totals -2532.87 USD; the remaining expected cash effect
is -448.52 USD. Together these account for the -2981.39 USD trade cash effect.
This is not an account cash balance. Short-sale proceeds are not assumed to be
freely withdrawable, and no margin or securities-borrow rules are modelled.

The manifest records the cutoff, missing confirmation, input manifest hash,
script hash and output file hashes. The missing-ID list is fixture evidence;
the later dbt reconciliation should find the unmatched trade by joining feeds,
not by reading that list.

Rerunning creates another delivery folder with the same confirmation IDs and
message content. It is a replay, not four new payments. Reuse the saved files
for retries; downstream ingestion must check event IDs across deliveries.

These confirmations are generated from the OMS inputs for a controlled test.
They are not independent real broker evidence. A real custodian would supply
its own settlement feed, often with matching identifiers requiring translation.

This step only creates local files. Loading them to Snowflake and matching
them to OMS_TRADE_CASH is the following lesson. No streaming service is running.
