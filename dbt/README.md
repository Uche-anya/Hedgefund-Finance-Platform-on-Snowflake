# dbt project

The active models calculate the two-year provisional equity close from RAW
events, historical prices and reviewed action decisions. See
[the model inventory](MODEL_INVENTORY.md) and
[the Snowflake path](../docs/two_year_snowflake_path.md).

dbt runs locally and sends its SQL to Snowflake. The helper uses the dedicated
encrypted dbt key and does not prompt for the Snowflake password.

From the repository root:

```powershell
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py debug
.\.venv\dbt\Scripts\python.exe scripts/dbt_dev.py build --select +fct_account_nav_daily --exclude tag:fixture
```

The second command builds the selected NAV model and its parents: the source
staging views, market-day and trade-obligation views, dated instrument seed,
review-decision seed, positions, cash and dividend balances. `build` also runs
selected data tests. The saved Python close is independent comparison evidence;
it is not an input to this NAV.

The two-year backfill and new business days use this same close graph. The
DEV Task graph has been run manually; its root is still unscheduled.
