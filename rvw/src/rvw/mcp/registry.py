"""Tool discovery and dispatch, independent of the MCP SDK (so it is unit-testable and reusable)."""
from __future__ import annotations

import fnmatch
import importlib
import inspect
import json
import os
import pkgutil
from typing import Any

from jsonschema import ValidationError
from jsonschema.validators import validator_for

import rvw

from . import worker
from .jobs import JobManager
from .spec import ToolError, ToolSpec, schema

MAX_TEXT = 400_000  # characters of JSON returned per call; larger results are cut with a note
SYNC_S = 20.0       # an isolated short tool answers inline if it ends within this many seconds
ISOLATE = "wave_*"  # tools isolated by default (RVW_MCP_ISOLATE); they parse big files in Python


def discover(only: set[str] | None = None) -> tuple[list[ToolSpec], list[str]]:
    """Tools from every `rvw.<pkg>.mcp_tools.mcp_tools()`. Returns (tools, problems)."""
    tools: list[ToolSpec] = []
    problems: list[str] = []
    for mod in sorted(pkgutil.iter_modules(rvw.__path__), key=lambda m: m.name):
        if not mod.ispkg or (only and mod.name not in only):
            continue
        name = f"rvw.{mod.name}.mcp_tools"
        try:
            m = importlib.import_module(name)
        except ModuleNotFoundError as e:
            if e.name == name:
                tools.extend(_command_tools(f"rvw.{mod.name}", problems))
                continue
            problems.append(f"{name}: {e}")
            continue
        except Exception as e:  # one broken package must not take the server down
            problems.append(f"{name}: {type(e).__name__}: {e}")
            continue
        try:
            tools.extend(m.mcp_tools())
        except Exception as e:
            problems.append(f"{name}.mcp_tools(): {type(e).__name__}: {e}")
        tools.extend(_command_tools(f"rvw.{mod.name}", problems))
    # Tool providers outside the rvw package: RVW_MCP_PLUGINS=module[,module...], each with mcp_tools().
    for name in filter(None, (x.strip() for x in os.environ.get("RVW_MCP_PLUGINS", "").split(","))):
        try:
            tools.extend(importlib.import_module(name).mcp_tools())
        except Exception as e:
            problems.append(f"plugin {name}: {type(e).__name__}: {e}")
    return tools, problems


def _command_tools(package: str, problems: list[str]) -> list[ToolSpec]:
    """Tools from `mcp_tools()` of each `<package>.commands` module (rvw.common.subcommands)."""
    from rvw.common.subcommands import command_modules
    try:
        modules = command_modules(package)
    except Exception as e:
        problems.append(f"{package}.commands: {type(e).__name__}: {e}")
        return []
    tools: list[ToolSpec] = []
    for module in modules:
        if hasattr(module, "mcp_tools"):
            try:
                tools.extend(module.mcp_tools())
            except Exception as e:
                problems.append(f"{module.__name__}.mcp_tools(): {type(e).__name__}: {e}")
    return tools


class Registry:
    def __init__(self, tools: list[ToolSpec], jobs: JobManager | None = None, sync_s: float | None = None,
                 max_text: int | None = None, project: str | None = None):
        self.project = project
        self.jobs = jobs or JobManager()
        self.sync_s = float(os.environ.get("RVW_MCP_SYNC_S", SYNC_S)) if sync_s is None else sync_s
        self.max_text = max_text or MAX_TEXT
        patterns = os.environ.get("RVW_MCP_ISOLATE", ISOLATE)
        self._isolate = [x.strip() for x in patterns.split(",") if x.strip()]
        self.tools: dict[str, ToolSpec] = {}
        self._validators = {}
        for t in tools + self._job_tools():
            if t.name in self.tools:
                raise ValueError(f"duplicate MCP tool name {t.name!r}")
            self.tools[t.name] = t
            validator = validator_for(t.input_schema)
            validator.check_schema(t.input_schema)
            self._validators[t.name] = validator(t.input_schema)

    @classmethod
    def discover(cls, only: set[str] | None = None, *, project: str | None = None) -> tuple["Registry", list[str]]:
        tools, problems = discover(only)
        return cls(tools, project=project), problems

    def call(self, name: str, arguments: dict | None) -> Any:
        """Runs a tool. Long tools return a job record at once. Raises ToolError for bad calls."""
        spec = self.tools.get(name)
        if spec is None:
            raise ToolError(f"unknown tool {name!r}")
        args = {} if arguments is None else arguments
        try:
            # Reject non-JSON numbers too: NaN can evade numeric bounds. Never coerce values
            # (in particular, the string "false" must not enable a boolean option).
            json.dumps(args, allow_nan=False)
            self._validators[name].validate(args)
        except (ValidationError, TypeError, ValueError) as exc:
            if isinstance(exc, ValidationError):
                path = ".".join(map(str, exc.absolute_path)) or "$"
                message = f"{path}: {exc.message}"
            else:
                message = str(exc)
            raise ToolError(f"bad arguments for {name}: {message}") from None
        args = dict(args)
        if (self.project is not None and "project" in spec.input_schema.get("properties", {})
                and "project" not in args and not args.get("core")):
            args["project"] = self.project
        if spec.long:
            def run(job):
                return spec.handler(**args, job=job) if spec.wants_job else spec.handler(**args)
            job = self.jobs.submit(name, args, run)
            return {"job_id": job.id, "status": job.status,
                    "note": "long-running: poll with job_status (wait_s up to 60 blocks until it finishes)"}
        target = self._isolated(spec)
        if target:
            return self._call_isolated(spec, args, *target)
        return spec.handler(**args)

    # ------------------------------------------------------------------ isolated short tools
    def _isolated(self, spec: ToolSpec) -> tuple[str, str] | None:
        """(module, function) when `spec` runs in a worker process, else None."""
        if not (spec.isolate or any(fnmatch.fnmatchcase(spec.name, p) for p in self._isolate)):
            return None
        module, qual = getattr(spec.handler, "__module__", None), getattr(spec.handler, "__qualname__", "")
        if not module or not qual.isidentifier():
            return None  # closures and methods cannot be named in another process: run in-process
        try:
            if getattr(importlib.import_module(module), qual) is not spec.handler:
                return None
        except (ImportError, AttributeError):
            return None
        return module, qual

    def _call_isolated(self, spec: ToolSpec, args: dict, module: str, function: str) -> Any:
        """Run in a worker process as a job. Answer inline if it ends within `sync_s`; otherwise
        hand back the job id, so a slow call can be followed and cancelled (job_cancel)."""
        inspect.signature(spec.handler).bind(**args)  # bad arguments fail here, as in-process
        job = self.jobs.submit(spec.name, args,
                               lambda job: worker.run_function(job, module, function, args), quick=True)
        if not job.done.wait(self.sync_s):
            return {"job_id": job.id, "status": job.state,
                    "note": f"{spec.name} took longer than {self.sync_s:g} s and continues as a background "
                            "job: poll job_status (wait_s up to 60) or stop it with job_cancel"}
        self.jobs.forget(job.id)
        if job.status == "done":
            return job.result
        if job.exception is not None:
            raise job.exception
        raise ToolError(f"{spec.name} {job.status}", {"log_tail": job.tail(20)})

    def call_json(self, name: str, arguments: dict | None) -> tuple[str, Any, bool]:
        """(text, structured, is_error) for the MCP result."""
        try:
            result = self.call(name, arguments)
            is_error = False
        except ToolError as e:
            result, is_error = {"error": str(e), **e.data}, True
        except TypeError as e:  # wrong arguments
            result, is_error = {"error": f"bad arguments for {name}: {e}"}, True
        except Exception as e:
            to_json = getattr(e, "to_json", None)
            result = to_json() if callable(to_json) else {"error": f"{type(e).__name__}: {e}"}
            is_error = True
        text, result = fit(result, self.max_text)
        return text, result if isinstance(result, dict) else {"result": result}, is_error

    # ---------------------------------------------------------------------------------- job tools
    def _job_tools(self) -> list[ToolSpec]:
        def status(job_id: str, wait_s: float = 0) -> dict:
            job = self._job(job_id)
            if wait_s and not job.done.is_set():
                job.done.wait(min(float(wait_s), 60.0))
            d = job.to_json()
            d["log_tail"] = job.tail(10)
            return d

        def log(job_id: str, tail: int = 100) -> dict:
            job = self._job(job_id)
            return {"job_id": job.id, "status": job.status, "lines": job.tail(int(tail))}

        def cancel(job_id: str) -> dict:
            job = self._job(job_id)
            job.cancel()  # SIGTERM the job's process groups, SIGKILL after Job.GRACE_S, reap
            job.done.wait(5)
            return job.to_json(with_result=False)

        def list_jobs() -> dict:
            return {"jobs": [j.to_json(with_result=False) for j in self.jobs.list()]}

        jid = {"job_id": {"type": "string", "description": "id returned by a long-running tool"}}
        return [
            ToolSpec("job_status", "Status of a background job started by a long-running tool; includes the result "
                     "when done. Pass wait_s (max 60) to block until it finishes.",
                     schema({**jid, "wait_s": {"type": "number", "minimum": 0, "default": 0}}, ["job_id"]), status),
            ToolSpec("job_log", "Last lines of a background job's log.",
                     schema({**jid, "tail": {"type": "integer", "minimum": 0, "default": 100}}, ["job_id"]), log),
            ToolSpec("job_cancel", "Cancel a background job: SIGTERM its process groups, SIGKILL after a grace "
                     "period. Returns the status (`cancelling` while a handler has not stopped yet).",
                     schema(jid, ["job_id"]), cancel),
            ToolSpec("job_list", "All background jobs of this server and their status.", schema({}), list_jobs),
        ]

    def _job(self, job_id: str):
        try:
            return self.jobs.get(job_id)
        except KeyError as e:
            raise ToolError(str(e)) from None


# -------------------------------------------------------------------------------- result size
def fit(result: Any, limit: int = MAX_TEXT) -> tuple[str, Any]:
    """(JSON text, value) of at most `limit` characters. A larger result keeps its shape: the
    longest lists and strings are shortened until it fits, and it gains `"truncated": true` and a
    `truncation` record (original size, what was cut). Always valid JSON."""
    text = json.dumps(result, indent=1, default=list)
    if len(text) <= limit:
        return text, result
    total = len(text)
    data = json.loads(text)  # a plain JSON copy that can be cut in place
    note = (f"result was {total} characters of JSON, over the {limit} limit; the listed lists and "
            "strings were shortened. Narrow the query (limit, depth, scope, a smaller window).")
    cuts: dict[str, dict] = {}
    # Room for the truncation record: up to 4000 characters, less for small limits (review 2 N7).
    reserve = min(4000, limit // 3)
    budget = limit - reserve
    max_cuts = max(0, min(40, (reserve - len(note) - 200) // 120))

    def wrap(value):
        info = {"note": note, "original_chars": total,
                "cuts": [{"path": k, **v} for k, v in list(cuts.items())[:max_cuts]]}
        if isinstance(value, dict):
            return {**value, "truncated": True, "truncation": info}
        return {"result": value, "truncated": True, "truncation": info}

    for _ in range(100):
        size = len(json.dumps(data, indent=1, default=list))
        if size <= budget:
            break
        found: list[tuple[int, str, Any, Any, Any]] = []  # (approximate size, path, parent, key, node)
        _measure(data, "$", None, None, found)
        if not found:
            break
        found.sort(key=lambda x: -x[0])
        n, path, parent, key, node = found[0]
        # Shrink the largest node by the excess, but keep at least a quarter of the budget for it
        # (or half of it, if it is already smaller), so one cut does not wipe a whole section.
        target = n - (size - budget) * 1.1 - 64
        if target < budget * 0.25:
            target = min(budget * 0.25, n * 0.5)
        if isinstance(node, list):
            keep = min(len(node) - 1, int(len(node) * target / n))
            cuts.setdefault(path, {"total": len(node)})["kept"] = keep
            del node[keep:]
        else:
            keep = min(len(node) - 1, int(target))
            cuts.setdefault(path, {"total": len(node)})["kept"] = keep
            parent[key] = node[:keep] + " ...[cut]"
    out = wrap(data)
    text = json.dumps(out, indent=1, default=list)
    if len(text) > limit:  # e.g. a huge dict of scalars: say so instead of returning a fragment
        out = wrap({})
        out["truncation"]["note"] = (f"result was {total} characters of JSON, over the {limit} limit, and "
                                     "could not be shortened; narrow the query (limit, depth, scope)")
        text = json.dumps(out, indent=1)
    if len(text) > limit:  # a very small limit: the shortest record that still says so
        out = {"truncated": True, "truncation": {"original_chars": total}}
        text = json.dumps(out)
        if len(text) > limit:
            out = {"truncated": True}
            text = json.dumps(out)
    return text, out


def _measure(node, path, parent, key, found) -> int:
    """Approximate JSON size of `node` (indent=1); records lists and long strings in `found`."""
    if isinstance(node, dict):
        size = 2
        for k, v in node.items():
            size += len(json.dumps(k)) + 4 + _measure(v, f"{path}.{k}", node, k, found)
        return size
    if isinstance(node, list):
        sizes = [_measure(v, f"{path}[{i}]", node, i, found) + 3 for i, v in enumerate(node)]
        size = 2 + sum(sizes)
        if len(node) > 1 and max(sizes) * 2 < size:  # else cut inside the one big item
            found.append((size, path, parent, key, node))
        return size
    size = len(json.dumps(node))
    if isinstance(node, str) and size > 1000 and parent is not None:
        found.append((size, path, parent, key, node))
    return size
