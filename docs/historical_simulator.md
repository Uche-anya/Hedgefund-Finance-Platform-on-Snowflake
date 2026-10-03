# First historical trade scenario

Run `python -m simulation.historical_simulator` from the project root.
It creates five fictional January 6, 2025 trades, using AAPL and AMZN closes
from January 3 in the verified assembled CSV. This is the same saved input
loaded into Snowflake; the simulator does not query the dbt view yet.

Each execution price is the previous close plus a small invented percentage
offset. One basis point is 0.01%; five basis points is 0.05%. These are scenario
inputs, not measured spreads or observed trades. Prices are rounded to cents.
We do not use January 6 closing prices or its daily high/low to manufacture
morning fills, because those values would not yet be known in the scenario.
This is not a trading-strategy backtest or an intraday execution model.

The five orders and quantities remain the original small lesson. We assume
short selling is allowed. Existing event fields retain is_simulated=true,
and new fields record the reference date, close, offset and pricing method.
AAPL.US and AMZN.US remain legacy labels, not independently verified security
master IDs; market_ticker is provided explicitly for the later price join.

This module supports only the fixed January 6 scenario, with the January 7
settlement date from the original simulator. It does not infer holiday-aware
settlement for arbitrary dates. Reference prices must exist on January 3;
there is no automatic fallback to older prices.

Output goes to a new data/simulator_historical scenario folder. The manifest
records the source snapshot and hashes of input prices and generated events.
Rerunning creates new trades, not retries. To replay a delivery later, reuse
its saved events. No data is uploaded and no positions are updated by this step.
