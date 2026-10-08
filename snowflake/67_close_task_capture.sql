-- Shared ownership for the manual Task graph and the local DEV runner.
USE ROLE SYSADMIN;

ALTER TABLE NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
    ADD COLUMN IF NOT EXISTS lease_owner VARCHAR;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_DEV.OPERATIONS.START_CLOSE_PILOT()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
var configured = snowflake.execute({
    sqlText: "select SYSTEM$GET_TASK_GRAPH_CONFIG('request_id')::varchar"
});
configured.next();
var requestId = configured.getColumnValue(1);
if (!/^[0-9a-f]{24}$/.test(requestId || '')) {
    throw new Error('Task graph needs a pinned request_id');
}
var runId = snowflake.execute({
    sqlText: "select SYSTEM$TASK_RUNTIME_INFO('CURRENT_TASK_GRAPH_RUN_GROUP_ID')"
});
runId.next();
runId = runId.getColumnValue(1);

function query(sql, binds) {
    return snowflake.execute({sqlText: sql, binds: binds || []});
}

query('alter session set LOCK_TIMEOUT = 0');
query('begin transaction');
try {
    var gate = query(`
        select build_gate from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_GATE
        where request_id = ?`, [requestId]);
    if (!gate.next() || gate.getColumnValue(1) !== 'BUILDABLE') {
        throw new Error('Pinned close inputs are blocked');
    }
    var active = query(`
        select count(*) from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
        where attempt_status = 'RUNNING'`);
    active.next();
    if (active.getColumnValue(1) !== 0) {
        throw new Error('An earlier close attempt is still marked RUNNING');
    }
    var lock = snowflake.createStatement({
        sqlText: `update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
                  set lease_owner = ?, touched_at = current_timestamp()
                  where lock_name = 'DAILY_CLOSE' and lease_owner is null`,
        binds: [runId]
    });
    lock.execute();
    if (lock.getNumRowsAffected() !== 1) {
        throw new Error('Close is already owned by another run');
    }
    query(`insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
          (attempt_id, request_id, started_at, attempt_status)
          values (?, ?, current_timestamp(), 'RUNNING')`, [runId, requestId]);
    query('commit');
    return runId;
} catch (error) {
    query('rollback');
    throw error;
}
$$;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_DEV.OPERATIONS.CAPTURE_CLOSE_PILOT()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
var configured = snowflake.execute({
    sqlText: "select SYSTEM$GET_TASK_GRAPH_CONFIG('request_id')::varchar, " +
             "SYSTEM$GET_TASK_GRAPH_CONFIG('supersedes_request_id')::varchar"
});
configured.next();
var requestId = configured.getColumnValue(1);
var predecessor = configured.getColumnValue(2) || null;
if (!/^[0-9a-f]{24}$/.test(requestId || '') ||
    (predecessor && !/^[0-9a-f]{24}$/.test(predecessor))) {
    throw new Error('Task graph needs a valid pinned request ID');
}
var run = snowflake.execute({
    sqlText: "select SYSTEM$TASK_RUNTIME_INFO('CURRENT_TASK_GRAPH_RUN_GROUP_ID')"
});
run.next();
var runId = run.getColumnValue(1);

function query(sql, binds) {
    return snowflake.execute({sqlText: sql, binds: binds || []});
}

function count(sql, binds) {
    var result = query(sql, binds);
    result.next();
    return result.getColumnValue(1);
}

query('alter session set LOCK_TIMEOUT = 0');
query('begin transaction');
try {
    var lock = snowflake.createStatement({
        sqlText: `update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
                  set touched_at = current_timestamp()
                  where lock_name = 'DAILY_CLOSE' and lease_owner = ?`,
        binds: [runId]
    });
    lock.execute();
    if (lock.getNumRowsAffected() !== 1) {
        throw new Error('This Task run does not own the close');
    }
    if (count(`select count(*) from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
               where attempt_id = ? and request_id = ?
                 and attempt_status = 'RUNNING'`, [runId, requestId]) !== 1) {
        throw new Error('Expected one running close attempt');
    }

    var request = query(`
        select r.scenario_id, r.business_date::varchar
        from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS r
        join NORTHBRIDGE_DEV.OPERATIONS.CLOSE_GATE g
          on r.request_id = g.request_id
        where r.request_id = ? and g.build_gate = 'BUILDABLE'
          and r.request_status = 'CANDIDATE'`, [requestId]);
    if (!request.next()) {
        throw new Error('Selected inputs changed during the dbt build');
    }
    var scenario = request.getColumnValue(1);
    var day = request.getColumnValue(2);

    var nav = query(`
        select count(*)::varchar, sum(reviewed_nav_usd)::varchar,
               hash_agg(hash(scenario_id, business_date, account_id,
                             settled_cash_usd, trade_receivable_usd,
                             trade_payable_usd, net_market_value_usd,
                             reviewed_dividend_receivable_usd,
                             reviewed_short_dividend_payable_usd,
                             reviewed_nav_usd, illustrative_nav_usd))::varchar
        from NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_NAV_DAILY
        where scenario_id = ? and business_date <= ?`, [scenario, day]);
    nav.next();
    var navRows = nav.getColumnValue(1);
    var navTotal = nav.getColumnValue(2);
    var navHash = nav.getColumnValue(3);

    var positions = query(`
        select count(*)::varchar, sum(market_value_usd)::varchar,
               hash_agg(hash(scenario_id, business_date, account_id,
                             security_id, quantity, close_price_usd,
                             market_value_usd))::varchar
        from NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_POSITIONS_DAILY
        where scenario_id = ? and business_date <= ?`, [scenario, day]);
    positions.next();
    var positionRows = positions.getColumnValue(1);
    var positionTotal = positions.getColumnValue(2);
    var positionHash = positions.getColumnValue(3);
    if (Number(navRows) === 0 || Number(positionRows) === 0) {
        throw new Error('Close tables are empty');
    }

    var saved = count(`select count(*) from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS
                       where request_id = ?`, [requestId]);
    var status;
    if (saved === 1) {
        var same = count(`
            select count(*) from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS
            where request_id = ? and supersedes_request_id is not distinct from ?
              and nav_rows = ? and nav_total = ? and nav_hash = ?
              and position_rows = ? and position_total = ? and position_hash = ?`,
            [requestId, predecessor, navRows, navTotal, navHash,
             positionRows, positionTotal, positionHash]);
        if (same !== 1) {
            throw new Error('Rerun differs from the saved candidate');
        }
        var rowCounts = query(`
            select record_type, count(*)
            from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
            where request_id = ? group by record_type`, [requestId]);
        var counts = {};
        while (rowCounts.next()) {
            counts[rowCounts.getColumnValue(1)] = rowCounts.getColumnValue(2);
        }
        if (counts.NAV !== Number(navRows) ||
            counts.POSITION !== Number(positionRows) ||
            Object.keys(counts).length !== 2) {
            throw new Error('Saved result rows are incomplete');
        }
        status = 'MATCHED';
    } else if (saved === 0) {
        if (predecessor) {
        var prior = count(`
            select count(*)
            from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS current_request
            join NORTHBRIDGE_DEV.OPERATIONS.CLOSE_REQUESTS previous_request
              on current_request.scenario_id = previous_request.scenario_id
             and current_request.business_date = previous_request.business_date
             and current_request.model_sha256 = previous_request.model_sha256
             and current_request.seed_sha256 = previous_request.seed_sha256
            join NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS previous_result
              on previous_result.request_id = previous_request.request_id
            where current_request.request_id = ?
              and previous_request.request_id = ?`, [requestId, predecessor]);
        if (prior !== 1) {
            throw new Error('The original saved version is missing or incompatible');
        }
        }
        query(`insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULTS
              (request_id, supersedes_request_id, attempt_id,
               nav_rows, nav_total, nav_hash, position_rows, position_total,
               position_hash, result_status)
              values (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CANDIDATE')`,
              [requestId, predecessor, runId, navRows, navTotal, navHash,
               positionRows, positionTotal, positionHash]);
        query(`insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
              (request_id, record_type, business_date, account_id,
               security_id, row_data)
              select ?, 'NAV', business_date, account_id, null,
                     object_construct_keep_null(*)
              from NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_NAV_DAILY
              where scenario_id = ? and business_date <= ?`,
              [requestId, scenario, day]);
        query(`insert into NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
              (request_id, record_type, business_date, account_id,
               security_id, row_data)
              select ?, 'POSITION', business_date, account_id, security_id,
                     object_construct_keep_null(*)
              from NORTHBRIDGE_DEV.DBT_DEV.FCT_ACCOUNT_POSITIONS_DAILY
              where scenario_id = ? and business_date <= ?`,
              [requestId, scenario, day]);
        if (count(`select count(*) from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
                   where request_id = ? and record_type = 'NAV'`, [requestId]) !== Number(navRows) ||
            count(`select count(*) from NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RESULT_ROWS
                   where request_id = ? and record_type = 'POSITION'`, [requestId]) !== Number(positionRows)) {
            throw new Error('Captured row counts differ from dbt');
        }
        status = 'SAVED';
    } else {
        throw new Error('Duplicate close result headers');
    }

    query(`update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
           set finished_at = current_timestamp(), attempt_status = ?
           where attempt_id = ? and attempt_status = 'RUNNING'`, [status, runId]);
    query(`update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
           set lease_owner = null, touched_at = current_timestamp()
           where lock_name = 'DAILY_CLOSE' and lease_owner = ?`, [runId]);
    query('commit');
    return status;
} catch (error) {
    query('rollback');
    throw error;
}
$$;

CREATE OR REPLACE PROCEDURE NORTHBRIDGE_DEV.OPERATIONS.FINISH_CLOSE_PILOT()
RETURNS VARCHAR
LANGUAGE JAVASCRIPT
EXECUTE AS CALLER
AS
$$
var run = snowflake.execute({
    sqlText: "select SYSTEM$TASK_RUNTIME_INFO('CURRENT_TASK_GRAPH_RUN_GROUP_ID')"
});
run.next();
var runId = run.getColumnValue(1);
function query(sql, binds) {
    return snowflake.execute({sqlText: sql, binds: binds || []});
}
query('alter session set LOCK_TIMEOUT = 0');
query('begin transaction');
try {
    var owner = snowflake.createStatement({
        sqlText: `update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_RUN_LOCK
                  set lease_owner = null, touched_at = current_timestamp()
                  where lock_name = 'DAILY_CLOSE' and lease_owner = ?`,
        binds: [runId]
    });
    owner.execute();
    if (owner.getNumRowsAffected() === 1) {
        query(`update NORTHBRIDGE_DEV.OPERATIONS.CLOSE_ATTEMPTS
               set finished_at = current_timestamp(), attempt_status = 'FAILED',
                   error_message = 'Task graph ended before result capture; inspect Task history'
               where attempt_id = ? and attempt_status = 'RUNNING'`, [runId]);
    }
    query('commit');
    return owner.getNumRowsAffected() === 1 ? 'RELEASED_FAILED_RUN' : 'NO_ACTIVE_LEASE';
} catch (error) {
    query('rollback');
    throw error;
}
$$;
