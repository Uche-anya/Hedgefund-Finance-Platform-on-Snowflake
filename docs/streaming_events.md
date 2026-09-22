# Execution events for the streaming demo

Status: proposed internal event contract and fictional fixture, not yet connected
to Snowflake. This is not a broker's FIX protocol or a claim about an existing OMS.
A production connector would translate its source messages into this format.

The fixture is `fixtures/streaming/execution_events.jsonl`: one JSON object per
line. Every identifier, timestamp and execution price is invented. The stock
identifier represents Apple, but these are not observed market executions.
The streaming_demo_001 scenario is separate from the saved two-trade delivery:
SIM-STREAM-E001 must never replace SIM-E001 or change its expected test values.

## Example lifecycle

1. The source reports a buy of 10 shares at a fictional USD 244.00.
2. The source corrects that same execution to 8 shares. The full corrected
   record is version 2 and explicitly supersedes the first event.
3. Re-delivering either event retains its event ID and identical contents.
   A retry is not another trade.

After both versions, the execution is 8 shares, not 18. Replaying version 1
after version 2 must not revert it to 10. This is a correction to a reported
execution, not an instruction to amend an unfilled order.

## Field meanings

| Field | Meaning |
| --- | --- |
| schema_version | Version of this message format; separate from trade version |
| event_id | Identifies one immutable message; retries reuse it |
| execution_id | Identifies the actual fill; multiple fills can share an order ID |
| execution_version | Increasing version assigned by the source for that fill |
| supersedes_event_id | Previous event being corrected |
| occurred_at | When the source recorded this event, including a later correction |
| published_at | When the source published the message |
| executed_at | Original fill time, preserved through the quantity correction |
| business_date | Source's trading date, not derived blindly from UTC date |
| account_id / broker_id | Account and broker identifiers, fictional in this fixture |
| quantity / execution_price | Decimal strings to avoid binary floating-point conversion |
| settlement_due | Expected payment date, not evidence that payment occurred |
| scenario_id / is_simulated | Keep demonstration data explicitly identifiable |

The ingestion service adds received_at, load/run identifiers and transport offset
information. The producer cannot truthfully populate Snowflake receipt time.
Original event times stay unchanged during historical replay; receipt times are
the actual replay ingestion times. Their difference is replay age, not live-feed
latency. Record replay publication time separately when measuring pipeline delay.

## Processing rules to implement

- Save raw received messages for audit, including arrival metadata.
- Deduplicate business processing by source_system, scenario_id and event_id.
  Same ID with different contents is an error to quarantine, not an update.
- Key execution state by source_system, scenario_id and execution_id. Validate
  the correction chain and select the latest valid version, not latest arrival.
  Missing predecessors remain pending; conflicting records for one version fail.
- A cancellation must be a new version referencing the prior event. Preserve
  its history but exclude the cancelled fill from current economic positions.
- Preserve original messages when corrections arrive; never erase history.
- Validate required IDs, timestamps, positive decimal quantities/prices for
  these equities, BUY/SELL sides, currency and known instrument mappings.
- Keep allocations in a separate event stream. An execution correction from
  10 to 8 does not automatically change a portfolio allocation from 10 to 8.
  Flag the mismatch until a corresponding allocation correction arrives.
- Test duplicate delivery, correction-before-original arrival, missing versions,
  cancellation, conflicting payloads and late allocation before promoting this
  from an example contract into an active ingestion pipeline.

Existing dbt staging models reject repeated execution IDs with different data.
They do not yet resolve event versions. Use separate event landing tables and
build current-state models before integrating this stream with holdings.
