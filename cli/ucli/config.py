import os

import yaml
from jsonschema import Draft202012Validator

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "seeds": {"type": "array", "items": {"type": "string"}},
        "hops": {"type": "integer", "minimum": 0, "maximum": 5},
        "contracts_paths": {"type": "array", "items": {"type": "string"}},
        "glossary_path": {"type": "string"},
        "seeds_for": {
            "type": "object",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
        "metrics": {
            "type": "object",
            "properties": {"enabled": {"type": "boolean"}},
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
    "required": ["hops"],
}


def load_config(path: str = ".understand-first.yml") -> dict:
    cfg = {
        "seeds": [],
        "hops": 2,
        "contracts_paths": [],
        "glossary_path": "docs/glossary.md",
        "seeds_for": {},
    }
    if not os.path.exists(path):
        return cfg
    try:
        data = yaml.safe_load(open(path, encoding="utf-8")) or {}
        if isinstance(data, dict):
            cfg.update(
                {k: v for k, v in data.items() if k in cfg or k == "seeds_for" or k == "metrics"}
            )
    except Exception:
        # fall back to defaults if YAML is malformed
        return cfg
    return cfg


def load_preset(label: str, path: str = ".understand-first.yml") -> list:
    c = load_config(path)
    return (c.get("seeds_for", {}) or {}).get(label, [])


def schema_keys() -> set:
    return set(SCHEMA["properties"].keys())


def filter_config_to_schema(data: dict) -> dict:
    """Keep only keys honored by runtime SCHEMA (source of truth)."""
    if not isinstance(data, dict):
        return {"hops": 2}
    out = {}
    for key in schema_keys():
        if key not in data:
            continue
        value = data[key]
        if key == "metrics":
            # SCHEMA only allows metrics.enabled
            enabled = False
            if isinstance(value, dict):
                enabled = bool(value.get("enabled", False))
            elif isinstance(value, bool):
                enabled = value
            out[key] = {"enabled": enabled}
        else:
            out[key] = value
    if "hops" not in out:
        out["hops"] = 2
    return out


def validate_config_dict(data: dict) -> list:
    validator = Draft202012Validator(SCHEMA)
    errors = []
    valid_keys = schema_keys()
    for err in validator.iter_errors(data):
        msg = err.message
        if err.validator == "additionalProperties":
            bad_key = list(err.instance.keys() - valid_keys)
            if bad_key:
                import difflib

                suggestion = difflib.get_close_matches(bad_key[0], list(valid_keys), n=1)
                if suggestion:
                    msg += f" (did you mean '{suggestion[0]}'?)"
        errors.append(msg)
    return errors
