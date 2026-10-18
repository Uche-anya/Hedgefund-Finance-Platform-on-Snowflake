"""Upload the dbt source to an internal stage and deploy it in Snowflake."""

import argparse
import os
import re
from pathlib import Path

from pipeline.environment import ENVIRONMENTS
from pipeline.load_day import snowflake_connection


TARGETS = ENVIRONMENTS

REQUIRED_RAW_TABLES = {
    "DAILY_OMS_EVENTS", "DAILY_PRICE_EVENTS", "DAILY_SETTLEMENT_EVENTS",
    "DAILY_OPENING_EVENTS", "DAILY_BANK_STATEMENTS", "DAILY_DELIVERIES",
    "DAILY_DIVIDEND_EVENTS", "DIVIDEND_REVIEWS", "DAILY_CLOSE_RUNS",
    "SECURITY_MAPPINGS",
}


def project_files(root):
    files = [root / "dbt_project.yml", root / "dbt_projects_profiles.yml"]
    files += sorted((root / "models").rglob("*.sql"))
    files += sorted((root / "models").rglob("*.yml"))
    files += sorted((root / "tests").rglob("*.sql"))
    for path in files:
        if not path.is_file():
            raise ValueError("Missing dbt file: {}".format(path))
    return files


def deploy(root, target, release_sha=None):
    env = TARGETS[target]
    database, schema, role = env.database, env.model_schema, env.dbt_role
    if release_sha and not re.fullmatch(r"[0-9a-f]{40}", release_sha):
        raise ValueError("Expected a full commit SHA")
    if os.environ.get("SNOWFLAKE_ROLE") != role:
        raise ValueError("{} deployment requires role {}".format(target, role))
    project = env.dbt("NORTHBRIDGE_DAILY")
    stage = env.dbt("DBT_SOURCE")
    folder = "commits/{}/".format(release_sha) if release_sha else "project/"
    source = "@{}/{}".format(stage, folder)
    with snowflake_connection(database=database, schema=schema) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT CURRENT_ROLE()")
            if cursor.fetchone()[0] != role:
                raise ValueError("Snowflake session has the wrong role")
            cursor.execute(
                "SELECT TABLE_NAME FROM {}.INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = 'RAW'".format(database)
            )
            present = {row[0] for row in cursor.fetchall()}
            missing = REQUIRED_RAW_TABLES - present
            if missing:
                raise ValueError("{} RAW is missing: {}".format(
                    database, ", ".join(sorted(missing))))
            cursor.execute("CREATE STAGE IF NOT EXISTS " + stage)
            for path in project_files(root):
                parent = path.relative_to(root).parent.as_posix()
                stage_path = source
                if parent != ".":
                    stage_path += parent + "/"
                uri = "file://" + path.resolve().as_posix()
                cursor.execute("PUT '{}' '{}' AUTO_COMPRESS = FALSE OVERWRITE = {}".format(
                    uri.replace("'", "''"), stage_path,
                    "FALSE" if release_sha else "TRUE"))
                print("Uploaded", path.relative_to(root))
            cursor.execute("SHOW DBT PROJECTS IN SCHEMA {}.{}".format(database, schema))
            exists = any(row[1] == "NORTHBRIDGE_DAILY" for row in cursor.fetchall())
            if exists:
                cursor.execute("ALTER DBT PROJECT " + project + " DEPLOY FROM '" + source + "'")
            else:
                cursor.execute("CREATE DBT PROJECT " + project + " FROM '" + source + "'" +
                               " DBT_VERSION = '1.12.3' DEFAULT_TARGET = '" + target +
                               "' AUTO_COMPILE = FALSE")
            print("Deployed", project, "from", source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path("dbt"))
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--release-sha", help="Keep this commit's uploaded source for rollback")
    args = parser.parse_args()
    try:
        deploy(args.project_dir.resolve(), args.target, args.release_sha)
    except (ValueError, OSError) as error:
        parser.exit(1, "Deployment stopped: {}\n".format(error))


if __name__ == "__main__":
    main()
