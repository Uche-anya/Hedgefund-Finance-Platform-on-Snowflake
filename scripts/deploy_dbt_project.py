"""Upload the dbt source to an internal stage and deploy it in Snowflake."""

import argparse
from pathlib import Path

from pipeline.load_day import snowflake_connection


PROJECT = "NORTHBRIDGE_DEV.DBT_DEV.NORTHBRIDGE_DAILY"
STAGE = "NORTHBRIDGE_DEV.DBT_DEV.DBT_SOURCE"


def project_files(root):
    files = [root / "dbt_project.yml", root / "dbt_projects_profiles.yml"]
    files += sorted((root / "models").rglob("*.sql"))
    files += sorted((root / "models").rglob("*.yml"))
    files += sorted((root / "tests").rglob("*.sql"))
    for path in files:
        if not path.is_file():
            raise ValueError("Missing dbt file: {}".format(path))
    return files


def deploy(root):
    with snowflake_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE STAGE IF NOT EXISTS " + STAGE)
            for path in project_files(root):
                parent = path.relative_to(root).parent.as_posix()
                target = "@{}/project/".format(STAGE)
                if parent != ".":
                    target += parent + "/"
                uri = "file://" + path.resolve().as_posix()
                cursor.execute("PUT '{}' '{}' AUTO_COMPRESS = FALSE OVERWRITE = TRUE".format(
                    uri.replace("'", "''"), target))
                print("Uploaded", path.relative_to(root))
            cursor.execute("SHOW DBT PROJECTS IN SCHEMA NORTHBRIDGE_DEV.DBT_DEV")
            exists = any(row[1] == "NORTHBRIDGE_DAILY" for row in cursor.fetchall())
            source = "'@{}/project/'".format(STAGE)
            if exists:
                cursor.execute("ALTER DBT PROJECT " + PROJECT + " DEPLOY FROM " + source)
            else:
                cursor.execute("CREATE DBT PROJECT " + PROJECT + " FROM " + source +
                               " DBT_VERSION = '1.12.3' DEFAULT_TARGET = 'dev' AUTO_COMPILE = FALSE")
            print("Deployed", PROJECT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("dbt"))
    args = parser.parse_args()
    try:
        deploy(args.project_dir.resolve())
    except (ValueError, OSError) as error:
        parser.exit(1, "Deployment stopped: {}\n".format(error))


if __name__ == "__main__":
    main()
