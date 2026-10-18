"""Run one saved close through the dbt project deployed in Snowflake."""

import argparse
from datetime import date
import os

from pipeline.load_day import snowflake_connection
from scripts.deploy_dbt_project import TARGETS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--opening-date", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--target", choices=TARGETS, required=True)
    args = parser.parse_args()
    business_date = date.fromisoformat(args.business_date).isoformat()
    opening_date = date.fromisoformat(args.opening_date).isoformat()
    if opening_date >= business_date:
        parser.error("Opening date must precede the close")

    env = TARGETS[args.target]
    database, schema, role = env.database, env.model_schema, env.dbt_role
    if os.environ.get("SNOWFLAKE_ROLE") != role:
        parser.error("{} run requires role {}".format(args.target, role))
    project = env.dbt("NORTHBRIDGE_DAILY")
    with snowflake_connection(database=database, schema=schema) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT CURRENT_ROLE()")
            if cursor.fetchone()[0] != role:
                parser.error("Snowflake session has the wrong role")
            cursor.execute(
                "EXECUTE DBT PROJECT " + project + " "
                "ARGS = 'build --target " + args.target + "' DBT_VERSION = '1.12.3' "
                "ENV_VARS = ('DBT_BUSINESS_DATE' = %s, "
                "'DBT_OPENING_DATE' = %s, 'DBT_SCENARIO_ID' = %s)",
                (business_date, opening_date, args.scenario)
            )
            for row in cursor.fetchall():
                print(row[0], row[1])
                if len(row) > 2:
                    print("\n".join(str(row[2]).splitlines()[-12:]))


if __name__ == "__main__":
    main()
