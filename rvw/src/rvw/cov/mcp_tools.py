"""Code, functional, formal and mutation coverage MCP tools."""
import os

from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler

# Proof and mutation jobs are heavy. They hold the machine-wide heavy-job lock named by
# $RVW_HEAVY_LOCK; unset, the platform's default from docs/PLATFORM_CONTRACTS.md (Resources).
# An empty value runs them without a lock. A `lock` argument overrides both per call.
DEFAULT_HEAVY_LOCK = "boom"


def heavy_lock(override: str | None = None) -> str | None:
    name = override if override is not None else os.environ.get("RVW_HEAVY_LOCK", DEFAULT_HEAVY_LOCK)
    return name or None


def _locked(action: str):
    def call(job, lock: str | None = None, **arguments):
        return handler("rvw.cov.cli", action, lock=heavy_lock(lock))(job, **arguments)
    return call


S = {"type": "string"}
B = {"type": "boolean"}
I = {"type": "integer"}
ARRAY = {"type": "array", "items": S, "minItems": 1}
DB = {"database": {**S, "description": "rvw.coverage/1 JSON database path"}}
OUT = {"out": {**S, "description": "also write JSON result to this path"}}
LOCK = {"lock": {**S, "description": "machine lock to hold (default $RVW_HEAVY_LOCK or the platform heavy-job "
                 "lock); empty string for none"}}


def mcp_tools():
    return [
        ToolSpec("cov_block_check", "Check declared block evidence against exact integration sources, tested parameters and assumptions. Reuse never covers new integration wiring.",
                 schema({"evidence":S,"integration":S},["evidence","integration"]),
                 handler("rvw.cov.block_evidence","block-check"),long=True),
        ToolSpec("cov_exchange", "Export/import the declared UCIS counter profile, or export native DAT/LCOV with metadata. Native metric kinds and exclusions are transported, never promoted to proof exclusions.",
                 schema({"database":S,"destination":S,"format":{"type":"string","enum":["ucis","import-ucis","dat","lcov"]}},["database","destination"]),
                 handler("rvw.cov.exchange_cli","exchange"),long=True),
        ToolSpec("cov_actions", "Generate bounded retirement sequence candidates with action graphs. Memory needs a declared writable data resource. Generation earns no hits or pipeline hazard evidence.",
                 schema({"goal": S, "work_dir": S, "registers": {"type":"array","items":I,"minItems":3,"maxItems":3},
                         "distances":{"type":"array","items":I}, "memory":B}, ["goal","work_dir","registers"]),
                 handler("rvw.cov.action_cli", "actions"), long=True),
        ToolSpec("cov_campaign", "Execute bounded ISA candidates through C1 and strict complete Spike checks. Resume validates saved artifacts. CPU-hour metrics remain unqualified.",
                 schema({"settings": S, "work_dir": S, "resume": B, "replay": {**I,"minimum":0}}, ["settings", "work_dir"]),
                 handler("rvw.cov.campaign_cli", "campaign"), long=True),
        ToolSpec("cov_generate", "Solve one declared pinned integer ISA goal with Z3. Emits a bounded payload and solver evidence. A generated candidate earns no coverage hits and is not a core correctness result.",
                 schema({"manifest": S, "source_root": S, "goal": S, "work_dir": S,
                         "registers": {"type": "array", "items": I, "minItems": 3, "maxItems": 3},
                         "seed": {**I, "default": 1}, "timeout_ms": {**I, "default": 1000}, **OUT},
                        ["manifest", "source_root", "goal", "work_dir", "registers"]),
                 handler("rvw.cov.cli", "generate"), long=True),
        ToolSpec("cov_closure", "List unhit bins with project-declared candidate tests. Suggestions are not hits.",
                 schema({"database": S, "candidates": S, "exclusions": S, **OUT}, ["database", "candidates"]),
                 handler("rvw.cov.cli", "closure"), long=True, annotations={"readOnlyHint": True}),
        ToolSpec("cov_rtl", "Sample typed RTL bins and bounded sequences from exact-instance samples. "
                 "Incomplete traces stay inconclusive. Unobserved bins are not unreachable.",
                 schema({"traces": ARRAY, "config": S, **OUT}, ["traces", "config"]),
                 handler("rvw.cov.cli", "rtl"), long=True, annotations={"readOnlyHint": True}),
        ToolSpec("cov_merge", "Merge per-test coverage.dat or C1/C3 results into a coverage database before reporting/ranking. "
                 "Retains source attribution and rejects incompatible point universes; large inputs run as a job.",
                 schema({"inputs": ARRAY, "source_root": {**S, "default": "."}, "scala_root": S,
                         "revision": S, "source_map": S, "design_db": S, "hgldd": {"type": "array", "items": S},
                         "dat": {**S, "description": "also write merged Verilator .dat and cross-check counts"}, **OUT}, ["inputs"]),
                 handler("rvw.cov.cli", "merge"), long=True),
        ToolSpec("cov_report", "Inspect hit rates, source attribution and never-hit coverage points; optionally apply proof exclusions "
                 "to measured hit rates. Large databases run as a job.",
                 schema({**DB, "exclusions": S}, ["database"]),
                 handler("rvw.cov.cli", "report"), long=True, annotations={"readOnlyHint": True}),
        ToolSpec("cov_rank", "Rank test contributions and choose a deterministic coverage-preserving test set. "
                 "exact proves minimum cardinality only for at most 20 tests. Runs as a job.",
                 schema({**DB, "exact": B}, ["database"]), handler("rvw.cov.cli", "rank"), long=True, annotations={"readOnlyHint": True}),
        ToolSpec("cov_select", "Select regression tests covering Scala changes in BASE..HEAD. Uses BASE-side mappings and "
                 "falls back to all tests when coverage cannot justify omissions. Runs as a job.",
                 schema({**DB, "diff": {**S, "description": "BASE..HEAD git revision range"},
                         "repo": {**S, "default": "."}}, ["database", "diff"]),
                 handler("rvw.cov.cli", "select"), long=True, annotations={"readOnlyHint": True}),
        ToolSpec("cov_functional", "Report RVFI functional coverage bins and holes from C2 traces or saved functional reports. "
                 "Use config for a declarative coverage plan; large traces run as a job.",
                 schema({"traces": ARRAY, "config": S, "manifest": S, "source_root": S,
                         "platform": {**S, "description": "platform name or JSON for the RVFI address convention "
                                      "(default: the bundled platform named by the trace header's core)"}}, ["traces"]),
                 handler("rvw.cov.cli", "functional"), long=True, annotations={"readOnlyHint": True}),
        ToolSpec("cov_prove", "Run bounded cover and unbounded safety proofs for reviewed coverage-point expressions. "
                 "Use a fresh work_dir; exclusions retain assumptions and hashes. The job holds the machine heavy-job lock "
                 "($RVW_HEAVY_LOCK, or `lock`; empty for none).",
                 schema({**DB, "config": S, "work_dir": S, "timeout": {**I, "minimum": 1, "default": 60}, **LOCK, **OUT},
                        ["database", "config", "work_dir"]), _locked("prove"), long=True),
        ToolSpec("cov_mutate", "Read historical MCY outcomes, or run a captured project with run=true after baseline validation. "
                 "To earn kills or equivalence, declare all external inputs in the project's rvw-external-inputs JSON list; "
                 "[] declares none. Legacy databases and saved runs without complete dependency captures stay "
                 "inconclusive with zero earned counts and retained observations. "
                 "Inspection uses saved detection and equivalence roles unless explicitly overridden. "
                 "The job holds the machine heavy-job lock ($RVW_HEAVY_LOCK, "
                 "or `lock`; empty for none).",
                 schema({"project": S, "run": B, "baseline": S, "timeout": {**I, "minimum": 1, "default": 120},
                         "jobs": {**I, "minimum": 1, "maximum": 4, "default": 1}, "test": ARRAY,
                         "equivalence_test": {"type": "array", "items": S}, **LOCK, **OUT}, ["project"]),
                 _locked("mutate"), long=True),
    ]
