"""Run one saved close through the dbt project deployed in Snowflake."""

import argparse
from datetime import date

from pipeline.load_day import snowflake_connection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--opening-date", required=True)
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()
    business_date = date.fromisoformat(args.business_date).isoformat()
    opening_date = date.fromisoformat(args.opening_date).isoformat()
    if opening_date >= business_date:
        parser.error("Opening date must precede the close")

    with snowflake_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "EXECUTE DBT PROJECT NORTHBRIDGE_DEV.DBT_DEV.NORTHBRIDGE_DAILY "
                "ARGS = 'build --target dev' DBT_VERSION = '1.12.3' "
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
