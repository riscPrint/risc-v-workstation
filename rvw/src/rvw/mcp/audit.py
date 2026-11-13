"""Static interface audit. Never executes a tool handler."""
from __future__ import annotations

import inspect
import re
from collections import Counter

ALIASES = {"output": "out", "output_dir": "out", "out_dir": "out",
           "run": "run_dir", "elf_path": "elf", "trace_path": "trace",
           "db_path": "db", "project_path": "project", "json_output": "json"}


def audit(registry, problems=()):
    rows = []
    for tool in registry.tools.values():
        findings = []
        def add(code, detail):
            findings.append({"code": code, "detail": detail})
        if not re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)+", tool.name):
            add("name_pattern", "Use package_verb; retain old names as aliases.")
        length = len(tool.description.strip())
        if length < 20 or length > 1000:
            add("description", f"Description has {length} characters; use 20 to 1000.")
        s = tool.input_schema
        for key in ("type", "properties", "required", "additionalProperties"):
            if key not in s:
                add("schema_field", key)
        for name, prop in s.get("properties", {}).items():
            if name in ALIASES:
                add("argument_alias", f"{name}: prefer {ALIASES[name]} for new tools.")
            if not any(k in prop for k in ("type", "$ref", "anyOf", "oneOf", "enum")):
                add("argument_schema", name)
        try:
            sig = inspect.signature(getattr(registry, "source_tools", {}).get(tool.name, tool).handler, follow_wrapped=False)
            if not any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
                for name in s.get("properties", {}):
                    if name not in sig.parameters:
                        add("handler_argument", name)
                for name, p in sig.parameters.items():
                    if name != "job" and p.default is p.empty and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY):
                        if name not in s.get("required", []):
                            add("handler_required", name)
        except (ValueError, TypeError):
            add("handler_signature", "Signature is not available.")
        if tool.side_effects is None:
            add("side_effects", "Declare read-only or writes-files.")
        if tool.native_tools is None:
            add("native_tools", "Declare inventory tool ids, or an empty tuple.")
        if not tool.result_envelope:
            add("result_envelope", "Legacy result; registry envelope is not enabled.")
        rows.append({"name": tool.name, "long": tool.long, "side_effects": tool.side_effects,
                     "native_tools": tool.native_tools, "findings": findings})
    counts = Counter(f["code"] for row in rows for f in row["findings"])
    return {"schema": "rvw.mcp-audit/1", "tools": rows, "problems": list(problems),
            "summary": {"tools": len(rows), "findings": sum(counts.values()), "by_code": dict(counts)}}


def debt(report):
    return sorted(f'{r["name"]}:{f["code"]}:{f["detail"]}'
                  for r in report["tools"] for f in r["findings"])
