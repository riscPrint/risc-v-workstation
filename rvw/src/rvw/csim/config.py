"""Study files (`rvw.csim-study/1`): JSON that describes the component models.

The native engine reads flat `key=value` lines and refuses keys it does not use, so
unknown knobs are errors. `source` and `name` are provenance only and stay in Python.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

SCHEMA = "rvw.csim-study/1"
SECTIONS = {"branch", "btb", "ras", "indirect", "wrong_path", "frontend", "memory", "mdp", "vp", "report"}
SCALARS = {"warmup_instructions", "simulation_instructions"}
META = {"schema", "name", "source", "description"}


def load(path_or_data) -> dict:
    if isinstance(path_or_data, dict):
        data = copy.deepcopy(path_or_data)
    else:
        data = json.loads(Path(path_or_data).read_text())
    if not isinstance(data, dict):
        raise ValueError("study must be a JSON object")
    validate(data)
    return data


def validate(data: dict) -> None:
    if data.get("schema", SCHEMA) != SCHEMA:
        raise ValueError(f"study schema must be {SCHEMA}")
    unknown = set(data) - SECTIONS - SCALARS - META
    if unknown:
        raise ValueError(f"unknown study keys: {', '.join(sorted(unknown))}")
    for k in SECTIONS & set(data):
        if not isinstance(data[k], dict):
            raise ValueError(f"study section {k} must be an object")
    src = data.get("source")
    if src is not None and not isinstance(src, dict):
        raise ValueError("source must be an object")
    if isinstance(src, dict) and src.get("fidelity") not in (None, "approximate", "unqualified"):
        raise ValueError("source.fidelity must be approximate or unqualified; no study claims RTL fidelity")


def _scalar(key: str, value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    if isinstance(value, str):
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key}: newline in value")
        return value
    raise ValueError(f"{key}: unsupported value type {type(value).__name__}")


def flatten(data: dict) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def walk(prefix: str, value):
        if isinstance(value, dict):
            if not value and prefix:
                raise ValueError(f"{prefix}: empty object")
            for k, v in value.items():
                if not isinstance(k, str) or not k or "." in k or "=" in k:
                    raise ValueError(f"invalid key {k!r} under {prefix or 'study'}")
                walk(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(f"{prefix}.{i}", v)
        elif value is None:
            raise ValueError(f"{prefix}: null value")
        else:
            out.append((prefix, _scalar(prefix, value)))

    for k, v in data.items():
        if k in META:
            continue
        walk(k, v)
    return out


def to_kv(data: dict) -> str:
    return "".join(f"{k}={v}\n" for k, v in flatten(data))


def set_path(data: dict, dotted: str, value) -> None:
    """Set `a.b.0.c` in nested dicts/lists, creating objects as needed."""
    parts = dotted.split(".")
    node = data
    for i, p in enumerate(parts):
        last = i == len(parts) - 1
        if isinstance(node, list):
            idx = int(p)
            while len(node) <= idx:
                node.append({})
            if last:
                node[idx] = value
            else:
                if not isinstance(node[idx], (dict, list)):
                    node[idx] = {}
                node = node[idx]
        else:
            if last:
                node[p] = value
            else:
                nxt = parts[i + 1]
                if p not in node or not isinstance(node[p], (dict, list)):
                    node[p] = [] if nxt.isdigit() else {}
                node = node[p]
    validate(data)


def parse_value(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
