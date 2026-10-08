"""Show whether a Snowflake dbt project is deployed for the DEV task pilot."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.register_close_request import connect


def main():
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SHOW DBT PROJECTS IN SCHEMA NORTHBRIDGE_DEV.OPERATIONS')
            rows = cursor.fetchall()
            columns = [column[0].lower() for column in cursor.description]
            names = [row[columns.index('name')] for row in rows]
            print('DEV dbt projects:', names)
            cursor.execute('SHOW TASKS IN SCHEMA NORTHBRIDGE_DEV.OPERATIONS')
            rows = cursor.fetchall()
            columns = [column[0].lower() for column in cursor.description]
            print('DEV tasks:', [(row[columns.index('name')],
                                  row[columns.index('state')]) for row in rows])
    finally:
        connection.close()


if __name__ == '__main__':
    main()
