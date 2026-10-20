"""Check a deployed dbt project and keep a record of the running commit."""

import argparse
from datetime import date
import os
import re

from pipeline.environment import get_environment
from pipeline.load_day import snowflake_connection


def check_role(cursor, env):
    if os.environ.get("SNOWFLAKE_ROLE") != env.dbt_role:
        raise ValueError("{} release requires {}".format(env.name, env.dbt_role))
    cursor.execute("SELECT CURRENT_ROLE()")
    if cursor.fetchone()[0] != env.dbt_role:
        raise ValueError("Snowflake session has the wrong role")


def compile_project(cursor, env):
    business_date = os.environ.get("DBT_BUSINESS_DATE", "2026-10-16")
    opening_date = os.environ.get("DBT_OPENING_DATE", "2026-10-07")
    scenario = os.environ.get("DBT_SCENARIO_ID", "sim-close-20261008")
    if env.name == "prod" and not all(os.environ.get(name) for name in (
            "DBT_BUSINESS_DATE", "DBT_OPENING_DATE", "DBT_SCENARIO_ID")):
        raise ValueError("PROD release needs its own close date, opening date and scenario")
    if date.fromisoformat(opening_date) >= date.fromisoformat(business_date):
        raise ValueError("Opening date must precede the close date")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", scenario):
        raise ValueError("Invalid scenario ID")
    cursor.execute(
        "EXECUTE DBT PROJECT " + env.dbt("NORTHBRIDGE_DAILY") + " "
        "ARGS = 'compile --target " + env.name + "' DBT_VERSION = '1.12.3' "
        "ENV_VARS = ('DBT_BUSINESS_DATE' = '" + business_date + "', "
        "'DBT_OPENING_DATE' = '" + opening_date + "', "
        "'DBT_SCENARIO_ID' = '" + scenario + "')"
    )
    result = cursor.fetchone()
    if not result or result[0] is not True:
        raise RuntimeError("Native dbt compile failed: {}".format(result))


def release_table(cursor, env):
    table = env.dbt("CODE_RELEASES")
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS " + table + " ("
        "COMMIT_SHA VARCHAR(40) NOT NULL, "
        "CI_RUN_ID NUMBER(38, 0) NOT NULL, "
        "DEPLOYED_AT TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP() NOT NULL, "
        "STAGE_PATH VARCHAR, ACTION VARCHAR)"
    )
    cursor.execute("ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS STAGE_PATH VARCHAR")
    cursor.execute("ALTER TABLE " + table + " ADD COLUMN IF NOT EXISTS ACTION VARCHAR")
    cursor.execute("UPDATE " + table + " SET STAGE_PATH = %s WHERE STAGE_PATH IS NULL",
                   ("@{}/project/".format(env.dbt("DBT_SOURCE")),))
    cursor.execute("UPDATE " + table + " SET ACTION = 'DEPLOY' WHERE ACTION IS NULL")
    return table


def stage_path(env, sha):
    return "@{}/commits/{}/".format(env.dbt("DBT_SOURCE"), sha)


def record_release(target, sha, ci_run_id):
    env = get_environment(target)
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected a full commit SHA")
    if not ci_run_id.isdigit():
        raise ValueError("Expected a numeric CI run ID")
    with snowflake_connection(database=env.database, schema=env.model_schema) as connection:
        with connection.cursor() as cursor:
            check_role(cursor, env)
            compile_project(cursor, env)
            table = release_table(cursor, env)
            cursor.execute(
                "INSERT INTO " + table +
                " (COMMIT_SHA, CI_RUN_ID, STAGE_PATH, ACTION) "
                "VALUES (%s, %s, %s, 'DEPLOY')",
                (sha, int(ci_run_id), stage_path(env, sha))
            )
            print("Compiled and recorded", env.name, sha)


def restore_last_release(target):
    env = get_environment(target)
    table = env.dbt("CODE_RELEASES")
    with snowflake_connection(database=env.database, schema=env.model_schema) as connection:
        with connection.cursor() as cursor:
            check_role(cursor, env)
            cursor.execute("DESCRIBE TABLE " + table)
            columns = {row[0].upper() for row in cursor.fetchall()}
            if "STAGE_PATH" in columns:
                cursor.execute("SELECT COMMIT_SHA, CI_RUN_ID, STAGE_PATH FROM " + table +
                               " ORDER BY DEPLOYED_AT DESC LIMIT 1")
            else:
                cursor.execute("SELECT COMMIT_SHA, CI_RUN_ID FROM " + table +
                               " ORDER BY DEPLOYED_AT DESC LIMIT 1")
            saved = cursor.fetchone()
            if not saved:
                raise ValueError("No earlier release is recorded")
            sha, ci_run_id = saved[:2]
            source = (saved[2] if len(saved) > 2 and saved[2]
                      else "@{}/project/".format(env.dbt("DBT_SOURCE")))
            allowed = re.fullmatch(
                r"@{}/(?:project|commits/[0-9a-f]{{40}})/".format(
                    re.escape(env.dbt("DBT_SOURCE"))), source)
            if not allowed:
                raise ValueError("Unsafe recorded stage path")
            cursor.execute("ALTER DBT PROJECT " + env.dbt("NORTHBRIDGE_DAILY") +
                           " DEPLOY FROM '" + source + "'")
            compile_project(cursor, env)
            release_table(cursor, env)
            cursor.execute(
                "INSERT INTO " + table +
                " (COMMIT_SHA, CI_RUN_ID, STAGE_PATH, ACTION) "
                "VALUES (%s, %s, %s, 'RESTORE')",
                (sha, ci_run_id, source)
            )
            print("Restored", env.name, sha, "from", source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "restore"))
    parser.add_argument("--target", choices=("dev", "test", "prod"), required=True)
    parser.add_argument("--sha")
    parser.add_argument("--ci-run-id")
    args = parser.parse_args()
    if args.action == "record":
        if not args.sha or not args.ci_run_id:
            parser.error("record requires --sha and --ci-run-id")
        record_release(args.target, args.sha, args.ci_run_id)
    else:
        restore_last_release(args.target)


if __name__ == "__main__":
    main()
