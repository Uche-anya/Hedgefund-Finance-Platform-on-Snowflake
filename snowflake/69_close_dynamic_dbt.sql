-- Use the request selected for this Task run, not a date baked into the Task.
USE ROLE SYSADMIN;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_DEV.OPERATIONS.RUN_CLOSE_DBT()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
var config = snowflake.execute({
    sqlText: "select SYSTEM$GET_TASK_GRAPH_CONFIG('request_id')::varchar"
});
config.next();
var requestId = config.getColumnValue(1);
if (!/^[0-9a-f]{24}$/.test(requestId || '')) {
    throw new Error('Task graph needs a pinned request_id');
}

var command = 'EXECUTE DBT PROJECT NORTHBRIDGE_DEV.OPERATIONS.NORTHBRIDGE_DBT ' +
              'ARGS = \'build --select +fct_account_nav_daily ' +
              '--exclude tag:fixture --target dev --vars "close_request_id: ' +
              requestId + '"\' ENVIRONMENT = \'dev\'';
var result = snowflake.execute({sqlText: command});
if (!result.next() || result.getColumnValue('SUCCESS') !== true) {
    throw new Error('dbt build failed for request ' + requestId);
}
return requestId;
$$;
