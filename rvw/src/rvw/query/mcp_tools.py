"""MCP tools of `rvw query` (convention: docs/PLATFORM_CONTRACTS.md, C7)."""
from __future__ import annotations

import os
from pathlib import Path

from rvw.mcp.spec import ToolError, ToolSpec, schema

from . import diff as diff_mod
from . import ops
from .db import QueryError, default_db, run_on


def _wrap(fn):
    def handler(db: str | None = None, project: str | None = None, **kw):
        try:
            from rvw.common.project import database
            selected_db, project_capture = database(db, project)
            result = run_on(selected_db or default_db(), lambda d: fn(d, **kw))
            if project_capture is not None:
                result["project_capture"] = project_capture
            return result
        except QueryError as e:
            raise ToolError(str(e), {k: v for k, v in e.to_json().items() if k != "error"}) from None
    return handler


def repo_root() -> Path:
    env = os.environ.get("RVW_ROOT")
    return Path(env) if env else Path(__file__).resolve().parents[4]


DB = {"project": {"type": "string", "description": "project file or directory"}, "db": {"type": "string", "description": "design database path (default: $RVW_DESIGNDB)"}}
SIG = {"signal": {"type": "string", "description": "signal: Verilog path (core.rob.rob_head), waveform path "
                  "(TOP.Top.core.rob.rob_head) or Spinal path (core.rob.io.enq.valids(0)); a unique suffix is enough"}}
IFACE = {"type": "string", "description": "signal, or a bundle/Area path standing for all its signals (an interface)"}
LIMIT = {"limit": {"type": "integer", "default": 500, "description": "maximum signals returned"}}
GRAPH = {"depth": {"type": "integer", "default": 1}, "stop_at_regs": {"type": "boolean", "default": False,
         "description": "do not expand past registers and memories"},
         "kinds": {"type": "array", "items": {"type": "string", "enum": sorted(ops.KIND_RANK)},
                   "description": "only these dependency kinds (data, cond, sel, init, blackbox)"},
         "include_clock": {"type": "boolean", "default": False,
                           "description": "include explicit clock-domain relations when stored; data uses are always kept"}, **LIMIT}
RO = {"readOnlyHint": True, "idempotentHint": True}


def _diff(old: str, new: str, scope: str | None = None, limit: int = 200, connections: bool = True) -> dict:
    try:
        return diff_mod.diff_files(old, new, scope=scope, limit=limit, connections=connections)
    except QueryError as e:
        raise ToolError(str(e), {k: v for k, v in e.to_json().items() if k != "error"}) from None


def _explain(old: str, new: str, coverage: str | None = None, effect: str | None = None,
             scope: str | None = None, limit: int = 500) -> dict:
    from .explain import explain
    return explain(old, new, coverage, effect, scope=scope, limit=limit)


def entries(root: Path | None = None) -> list[str]:
    """Named design entries of build-db.sh: directories SpinalDB/<entry> with build.sbt and entry.sh."""
    base = (root or repo_root()) / "SpinalDB"
    return sorted(d.name for d in base.iterdir() if (d / "entry.sh").is_file() and (d / "build.sbt").is_file()) \
        if base.is_dir() else []


def _build_db(out: str, design: str | None = None, entry: str | None = None, config: str | None = None,
              sbt_dir: str | None = None, test_classpath: bool = False, options: list[str] | None = None,
              job=None, project=None) -> dict:
    from rvw.common.project import find_project
    if not design and not entry and find_project(project):
        from .project import build_database
        return build_database(project, config, out, job=job, options=options)
    if project is not None:
        raise ToolError("project build cannot also select design or entry")
    script = repo_root() / "SpinalDB" / "build-db.sh"
    if not script.exists():
        raise ToolError(f"{script} not found (set RVW_ROOT to the risc-v-workstation checkout)")
    if bool(design) == bool(entry):
        raise ToolError("give exactly one of `design` (component class) or `entry` (a named entry, with `config`)")
    if entry:
        known = entries()
        if entry not in known:
            raise ToolError(f"unknown entry {entry!r}", {"entries": known})
        if not config:
            raise ToolError(f"entry {entry!r} needs `config`")
        cmd = [str(script), entry, config, out]
    else:
        cmd = [str(script), "class", design, out] + (["--sbt-dir", sbt_dir] if sbt_dir else []) + \
              (["--test"] if test_classpath else [])
    cmd += list(options or [])
    job.set_progress("elaborating")
    rc = job.run(cmd)
    if rc != 0:
        raise ToolError(f"build-db.sh failed with exit code {rc}; see job_log")
    return run_on(out, ops.info)


def _build_hdl(sources: list, top: str, out: str, frontend: str = "yosys", include_dirs: list | None = None,
               defines: list | None = None, parameters: list | None = None, std: str | None = None,
               library: str = "work", source_roots: list | None = None, timeout: int = 300, cache_dir: str | None = None) -> dict:
    from .hdl import build_hdl
    try:
        result = build_hdl(sources, top, out, frontend=frontend, include_dirs=include_dirs or (),
                           defines=defines or (), parameters=parameters or (), std=std, library=library,
                           source_roots=source_roots or (), timeout=timeout, cache_dir=cache_dir)
    except (ValueError, OSError) as e:
        raise ToolError(str(e)) from None
    return {**result, "info": run_on(out, ops.info)}


def mcp_tools() -> list[ToolSpec]:
    return [
        ToolSpec("query_build_hdl", "Build a navigation design database from Verilog/SystemVerilog sources so "
                 "every query_* and lint tool works on a non-Spinal core. frontend 'yosys' takes the native "
                 "read_verilog -sv subset (self-contained files); 'slang' elaborates full SystemVerilog through "
                 "yosys-slang with include directories, defines and top parameters, and records per-instance "
                 "parameters (artifact hdl/parameters.json) and declared SV types; 'ghdl' elaborates VHDL "
                 "through the GHDL Yosys plugin (parameters are top generics, std 93/08, library the work "
                 "library) with VHDL declaration and assignment lines; 'chisel' takes one FIRRTL file "
                 "through firtool ($RVW_FIRTOOL), maps locations to Scala lines under source_roots, accepts "
                 "Chisel names (io.a.valid) and stores the emitted Verilog and HGLDD.",
                 schema({"sources": {"type": "array", "items": {"type": "string"}}, "top": {"type": "string"},
                         "out": {"type": "string"}, "frontend": {"type": "string", "enum": ["yosys", "slang", "ghdl", "chisel"],
                                                                 "default": "yosys"},
                         "include_dirs": {"type": "array", "items": {"type": "string"}},
                         "defines": {"type": "array", "items": {"type": "string"}, "description": "NAME[=VALUE]"},
                         "parameters": {"type": "array", "items": {"type": "string"}, "description": "NAME=VALUE"},
                         "std": {"type": "string"}, "library": {"type": "string", "default": "work"},
                         "cache_dir": {"type": "string", "description": "source-hash cache outside source directories"},
                         "source_roots": {"type": "array", "items": {"type": "string"}}, "timeout": {"type": "integer", "default": 300}},
                        ["sources", "top", "out"]),
                 _build_hdl),
        ToolSpec("query_info", "What a design database holds: toplevel, configuration, counts, clock domains, "
                 "artifacts (blocks, pdg, hgldd), RTL files, warnings.", schema(DB), _wrap(ops.info), annotations=RO),
        ToolSpec("query_where", "Where a signal (or bundle/Area) is: Scala source line, Verilog module/name/line, "
                 "waveform path, Spinal path, type, width, clock domain and reset value.",
                 schema({**DB, **SIG}, ["signal"]), _wrap(lambda d, signal: ops.where(d, signal)), annotations=RO),
        ToolSpec("query_drivers", "What drives a signal: every assignment with its source expression, when/switch "
                 "conditions, enables, Scala location; for registers the clock, reset signal/kind/value; for "
                 "memories the ports. Assignments are in elaboration order (later wins).",
                 schema({**DB, **SIG}, ["signal"]), _wrap(lambda d, signal: ops.drivers(d, signal)), annotations=RO),
        ToolSpec("query_loads", "What reads a signal: reader signals with how (data, cond, sel), the statements "
                 "and the conditions that use it.", schema({**DB, **SIG, **LIMIT}, ["signal"]),
                 _wrap(lambda d, signal, limit=500: ops.loads(d, signal, limit=limit)), annotations=RO),
        ToolSpec("query_fanin", "Transitive drivers of a signal or interface up to `depth`, through logic "
                 "(compiler temporaries are transparent). Lists signals, edges, registers and ports reached.",
                 schema({**DB, "signal": IFACE, **GRAPH}, ["signal"]),
                 _wrap(lambda d, signal, **kw: ops.fanin(d, signal, **kw)), annotations=RO),
        ToolSpec("query_fanout", "Transitive readers of a signal or interface up to `depth` (see query_fanin).",
                 schema({**DB, "signal": IFACE, **GRAPH}, ["signal"]),
                 _wrap(lambda d, signal, **kw: ops.fanout(d, signal, **kw)), annotations=RO),
        ToolSpec("query_path", "Shortest dependency paths from `a` (read) to `b` (driven): each hop with the "
                 "statement linking it and its Scala location, and the number of register stages. "
                 "comb_only stops at registers, memories and synchronous read state; data_only ignores conditions and selects.",
                 schema({**DB, "a": IFACE, "b": IFACE, "comb_only": {"type": "boolean", "default": False},
                         "data_only": {"type": "boolean", "default": False},
                         "max_paths": {"type": "integer", "default": 3}}, ["a", "b"]),
                 _wrap(lambda d, a, b, **kw: ops.path(d, a, b, **kw)), annotations=RO),
        ToolSpec("query_search", "Find signals and components by name: substring, glob (*, ?) or regex; "
                 "filter by kind (reg, wire, port, mem, component) and scope (component path).",
                 schema({**DB, "pattern": {"type": "string"}, "kind": {"type": "string",
                         "enum": ["reg", "wire", "port", "mem", "component"]}, "regex": {"type": "boolean", "default": False},
                         "scope": {"type": "string"}, "include_generated": {"type": "boolean", "default": False},
                         "limit": {"type": "integer", "default": 100}}, ["pattern"]),
                 _wrap(lambda d, pattern, **kw: ops.search(d, pattern, **kw)), annotations=RO),
        ToolSpec("query_hierarchy", "Component tree below `path` (default: toplevel): instance names, Verilog "
                 "modules, Scala classes, source locations.",
                 schema({**DB, "path": {"type": "string"}, "depth": {"type": "integer", "default": 2}}),
                 _wrap(lambda d, path=None, depth=2: ops.hierarchy(d, path, depth)), annotations=RO),
        ToolSpec("query_component", "One component: ports, interfaces (Stream/Flow/bundles), children, registers, "
                 "memories, Areas, counts.", schema({**DB, "path": {"type": "string"}}),
                 _wrap(lambda d, path=None: ops.component(d, path)), annotations=RO),
        ToolSpec("query_regs", "Registers of a component (recursive: of its subtree) with width, clock, reset "
                 "value and Scala location.", schema({**DB, "path": {"type": "string"},
                                                       "recursive": {"type": "boolean", "default": False},
                                                       "include_generated": {"type": "boolean", "default": False}}),
                 _wrap(lambda d, path=None, **kw: ops.regs(d, path, **kw)), annotations=RO),
        ToolSpec("query_diff", "What changed in the elaborated hardware between two databases (e.g. before and "
                 "after a Scala edit): components, ports, registers, memories, signals, connections between "
                 "named signals, and the logic of each changed signal.",
                 schema({"old": {"type": "string"}, "new": {"type": "string"}, "scope": {"type": "string"},
                         "limit": {"type": "integer", "default": 200},
                         "connections": {"type": "boolean", "default": True}}, ["old", "new"]),
                 _diff, annotations=RO),
        ToolSpec("query_explain", "Explain a design diff: each hardware difference with its Scala locations, the "
                 "tests that hit base coverage points on those lines (coverage: rvw.coverage/1 of the OLD revision), "
                 "and a measured effect of the whole change (effect: perf/arch compare JSON). Uncertain items make "
                 "the test selection 'all'.",
                 schema({"old": {"type": "string"}, "new": {"type": "string"}, "coverage": {"type": "string"},
                         "effect": {"type": "string"}, "scope": {"type": "string"},
                         "limit": {"type": "integer", "default": 500}}, ["old", "new"]),
                 _explain, annotations=RO),
        ToolSpec("query_export", "Write an artifact stored in the database to a file: `blocks` (SpinalBlocks "
                 "diagram JSON), `pdg` (SpinalTrace PDG JSON), `hgldd` (SpinalWaves HGLDD for Surfer).",
                 schema({**DB, "artifact": {"type": "string"}, "out": {"type": "string"}}, ["artifact", "out"]),
                 _wrap(lambda d, artifact, out: ops.export(d, artifact, out))),
        ToolSpec("query_build_db", "Elaborate a design and write its design database (minutes for a CPU). Either "
                 "`design` (a Spinal component class with a no-argument constructor, on the classpath of `sbt_dir`, "
                 "default SpinalDB/spinaldb) or `entry` plus `config`: a named entry of SpinalDB/build-db.sh "
                 f"(here: {', '.join(entries()) or 'none'}) and its configuration. An entry holds the machine "
                 "lock it declares. Returns a job id.",
                 schema({"project": {"type": "string"}, "out": {"type": "string"}, "design": {"type": "string"},
                         "entry": {"type": "string", "description": "named entry: a directory SpinalDB/<entry>"},
                         "config": {"type": "string", "description": "configuration of the entry"},
                         "sbt_dir": {"type": "string"}, "test_classpath": {"type": "boolean", "default": False},
                         "options": {"type": "array", "items": {"type": "string"},
                                     "description": "extra SpinalDB options, e.g. --no-pdg, --source-root DIR"}},
                        ["out"]),
                 _build_db, long=True),
    ]
