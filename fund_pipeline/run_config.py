"""Read the dates and saved input locations for one pipeline run."""

from datetime import date
import hashlib
import json
from pathlib import Path


PATH_FIELDS = ("delivery", "references", "fx_delivery", "gbp_references", "database", "run_root")
DATE_FIELDS = ("business_date", "as_of")


def unique_fields(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f"Duplicate configuration field: {name}")
        result[name] = value
    return result


def read_config(path):
    path = path.resolve()
    raw = path.read_bytes()
    settings = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_fields)
    fields = set(PATH_FIELDS + DATE_FIELDS)
    if not isinstance(settings, dict) or set(settings) != fields:
        raise ValueError("Configuration must contain exactly: " + ", ".join(PATH_FIELDS + DATE_FIELDS))
    for name, value in settings.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Configuration field {name} must be nonempty text")
    for name in DATE_FIELDS:
        if date.fromisoformat(settings[name]).isoformat() != settings[name]:
            raise ValueError(f"Use YYYY-MM-DD for {name}")
    if settings["business_date"] > settings["as_of"]:
        raise ValueError("Valuation date must be on or after the trade batch date")
    resolved = dict(settings)
    for name in PATH_FIELDS:
        # Relative paths belong to the configuration's folder, not the terminal.
        resolved[name] = (path.parent / Path(settings[name])).resolve()
    evidence = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "settings": settings}
    return resolved, evidence
