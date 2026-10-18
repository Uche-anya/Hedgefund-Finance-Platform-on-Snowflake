"""Snowflake names used by the same pipeline in each environment."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Environment:
    name: str
    database: str
    model_schema: str

    @property
    def dbt_role(self):
        return "NORTHBRIDGE_DBT_" + self.name.upper()

    def raw(self, name):
        return "{}.RAW.{}".format(self.database, name)

    def dbt(self, name):
        return "{}.{}.{}".format(self.database, self.model_schema, name)


ENVIRONMENTS = {
    "dev": Environment("dev", "NORTHBRIDGE_DEV", "DBT_DEV"),
    "test": Environment("test", "NORTHBRIDGE_TEST", "DBT_TEST"),
    "prod": Environment("prod", "NORTHBRIDGE_PROD", "DBT_PROD"),
}


def get_environment(name=None):
    selected = name or os.environ.get("NORTHBRIDGE_ENV", "dev")
    try:
        return ENVIRONMENTS[selected.lower()]
    except KeyError:
        raise ValueError("Unknown Northbridge environment: {}".format(selected))
