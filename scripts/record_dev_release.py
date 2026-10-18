"""Compile the deployed DEV project and record the commit that passed."""

import argparse
import os
import re

from pipeline.load_day import snowflake_connection


PROJECT = "NORTHBRIDGE_DEV.DBT_DEV.NORTHBRIDGE_DAILY"
RELEASES = "NORTHBRIDGE_DEV.DBT_DEV.CODE_RELEASES"


def record_release(sha, ci_run_id):
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Expected a full commit SHA")
    if not ci_run_id.isdigit():
        raise ValueError("Expected a numeric CI run ID")
    if os.environ.get("SNOWFLAKE_ROLE") != "NORTHBRIDGE_DBT_DEV":
        raise ValueError("DEV release requires NORTHBRIDGE_DBT_DEV")

    with snowflake_connection(database="NORTHBRIDGE_DEV", schema="DBT_DEV") as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT CURRENT_ROLE()")
            if cursor.fetchone()[0] != "NORTHBRIDGE_DBT_DEV":
                raise ValueError("Snowflake session has the wrong role")

            cursor.execute(
                "EXECUTE DBT PROJECT " + PROJECT + " "
                "ARGS = 'compile --target dev' DBT_VERSION = '1.12.3' "
                "ENV_VARS = ('DBT_BUSINESS_DATE' = '2026-10-16', "
                "'DBT_OPENING_DATE' = '2026-10-07', "
                "'DBT_SCENARIO_ID' = 'sim-close-20261008')"
            )
            result = cursor.fetchone()
            if not result or result[0] is not True:
                raise RuntimeError("Native dbt compile failed: {}".format(result))

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS " + RELEASES + " ("
                "COMMIT_SHA VARCHAR(40) NOT NULL, "
                "CI_RUN_ID NUMBER(38, 0) NOT NULL, "
                "DEPLOYED_AT TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP() NOT NULL)"
            )
            cursor.execute(
                "INSERT INTO " + RELEASES + " (COMMIT_SHA, CI_RUN_ID) VALUES (%s, %s)",
                (sha, int(ci_run_id))
            )
            print("DEV dbt project compiled; recorded commit", sha)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--ci-run-id", required=True)
    args = parser.parse_args()
    record_release(args.sha, args.ci_run_id)


if __name__ == "__main__":
    main()
