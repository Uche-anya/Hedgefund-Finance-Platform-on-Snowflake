"""Record one checked TEST or PROD close after a successful dbt build."""

import argparse
from datetime import date
import os

from pipeline.environment import get_environment
from pipeline.load_day import snowflake_connection


def record(business_date, opening_date, scenario):
    env = get_environment()
    if env.name not in ("test", "prod") or os.environ.get("SNOWFLAKE_ROLE") != env.dbt_role:
        raise ValueError("Use the TEST or PROD dbt role")
    if date.fromisoformat(opening_date) >= date.fromisoformat(business_date):
        raise ValueError("Opening date must precede the close")

    with snowflake_connection(database=env.database, schema=env.model_schema) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT CURRENT_ROLE()")
            if cursor.fetchone()[0] != env.dbt_role:
                raise ValueError("Snowflake session has the wrong role")

            cursor.execute(
                "SELECT n.account_id, n.nav_usd, c.reconciliation_status "
                "FROM " + env.dbt("FCT_NAV_DAILY") + " n LEFT JOIN "
                + env.dbt("FCT_CASH_RECONCILIATION") + " c "
                "ON c.account_id = n.account_id AND c.scenario_id = n.scenario_id "
                "AND c.statement_date = n.valuation_date "
                "WHERE n.valuation_date = TO_DATE(%s) AND n.scenario_id = %s",
                (business_date, scenario)
            )
            navs = cursor.fetchall()
            accounts = {row[0] for row in navs}
            if len(navs) != 2 or len(accounts) != 2 or any(
                    row[1] is None or row[2] != "MATCH" for row in navs):
                raise ValueError("Close needs two NAVs and two matching bank balances")

            runs = env.raw("DAILY_CLOSE_RUNS")
            cursor.execute(
                "SELECT COUNT(*) FROM " + runs + " WHERE business_date = TO_DATE(%s) "
                "AND scenario_id = %s AND status = 'VALIDATED'",
                (business_date, scenario)
            )
            count = cursor.fetchone()[0]
            if count > 1:
                raise ValueError("More than one validated close")
            if count == 1:
                print("Close already validated")
                return

            cursor.execute(
                "INSERT INTO " + runs + " (run_id, business_date, scenario_id, "
                "opening_date, status, detail, finished_at) "
                "SELECT UUID_STRING(), TO_DATE(%s), %s, TO_DATE(%s), 'VALIDATED', "
                "'dbt build and bank reconciliation passed', "
                "CURRENT_TIMESTAMP()",
                (business_date, scenario, opening_date)
            )
            print("Validated", env.name.upper(), "close for", business_date, scenario)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("business_date")
    parser.add_argument("--opening-date", required=True)
    parser.add_argument("--scenario", required=True)
    args = parser.parse_args()
    record(args.business_date, args.opening_date, args.scenario)


if __name__ == "__main__":
    main()
