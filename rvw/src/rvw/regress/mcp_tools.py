"""Regression MCP tools, using the CLI's structured Python API (contract C7)."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler
from .cli import execute_json

S = {"type": "string"}
B = {"type": "boolean"}
I = {"type": "integer"}
N = {"type": "number"}
CORE = {"project": {**S, "description": "project file or directory; defaults to RVW_PROJECT or discovery"}, "core": {**S, "description": "core config name or TOML path; defaults to RVW_CORE"}}
RO = {"readOnlyHint": True}
RUN = {"jobs": {**I, "minimum": 1}, "seeds": {**I, "minimum": 1},
       "seed_base": {**I, "default": 1}, "random_seeds": B,
       "filter": {"type": "array", "items": S, "description": "test-id regexes"},
       "max_cycles": I, "timeout": {**N, "exclusiveMinimum": 0}, "rvfi_trace": B, "no_cache": B,
       "replay_max_bytes": {**I, "minimum": 1,
                            "description": "Unique replay ELF byte limit; default 268435456. Checked before execution."}}
BUDGET = {"budget_cpu_seconds": {**N, "exclusiveMinimum": 0}, "budget_wall_seconds": {**N, "exclusiveMinimum": 0},
          "budget_job_count": {**I, "minimum": 1}, "cost_report": S}
COMPARE = {**CORE, "known": S, "perf_tolerance": N, "allow_missing": B,
           "seed_policy": {**S, "enum": ["auto", "exact", "count"], "default": "auto"}}


def _call(action):
    def call(**arguments):
        return execute_json(action, **arguments)
    return call


def mcp_tools():
    from .mmu_iommu import mcp_run, generate
    return [
        ToolSpec("regress_sail_tests", "Generate bounded directed test fragments for the three pinned RV32 Sail arithmetic rules. Expected values come from a complete DII oracle stream. No DUT pass or endpoint identity attestation is granted.",
                 schema({"model":{"type":"string"},"work_dir":{"type":"string"},"sail_endpoint":{"type":"string"},
                         "registers":{"type":"array","items":{"type":"integer"},"minItems":4,"maxItems":4},
                         "instructions":{"type":"array","items":{"type":"string","enum":["add","sub","addi"]}},
                         "seed":{"type":"integer"},"cases":{"type":"integer"},"timeout":{"type":"number"}},
                        ["model","work_dir","sail_endpoint","registers"]),
                 handler("rvw.regress.sail_tests","sail-tests"),long=True, side_effects='long-running; launches a supplied Sail endpoint; writes generated programs under work_dir', native_tools=()),
        ToolSpec('regress_mmu_iommu_generate', 'Generate decoded IOMMU translation, isolation, queue and MSI scenario data. This is not a DUT run.', schema({'seed': I, 'mode': {**S, 'enum': ['sv39', 'sv48', 'sv57']}}), generate, annotations=RO, side_effects='read-only', native_tools=()),
        ToolSpec('regress_mmu_iommu', 'Compare decoded IOMMU scenario steps with independently captured device responses. A consistent result requires C1 binding. Raw context and register conformance remain unsupported.', schema({'description': S, 'observations': S, 'result': S}, ['description']), mcp_run, annotations=RO, side_effects='read-only', native_tools=()),
        ToolSpec("regress_random", "Generate pinned riscv-dv programs, compile project runtime, run C1 and compare complete C2 with Spike. Only qualified runs earn functional coverage. Generator, compiler, adapter and comparison errors remain separate.",
                 schema({**CORE, "settings": S, "out": S, "config": S,
                         "seeds": {**I, "minimum": 1, "default": 1},
                         "seed_base": {**I, "default": 1}, "resume": B,
                         "jobs": {**I, "minimum": 1, "maximum": 4, "default": 1}}, ["out"]),
                 handler("rvw.regress.random_stream"), long=True, side_effects='long-running; launches generator, compiler, project adapter and Spike; writes campaign under out', native_tools=('riscv-dv', 'RISC-V GCC', 'Spike')),
        ToolSpec("regress_list", "Discover a core's suites, tiers and configurations before running; pass suite to list test IDs.",
                 schema({**CORE, "suite": S}), _call("list"), annotations=RO, side_effects='read-only', native_tools=()),
        ToolSpec("regress_run", "Run suites or a tier through the core adapter, resume/cache results, or preview with dry_run. "
                 "source and rev are mutually exclusive. "
                 "Use regress_compare or regress_gate for an accept/reject decision. Returns a job; the runner takes the core lock.",
                 schema({**CORE, **RUN, "suite": {**S, "description": "comma-separated suites; give suite or tier"},
                         "tier": S, "config": {**S, "description": "comma-separated configurations"},
                         "out": S, "rev": S, "source": S, "fresh": B, "no_index": B, "dry_run": B}),
                 handler("rvw.regress.cli", "run"), long=True, side_effects='long-running; launches project native adapter and revision builds; writes run artifacts and history under project output', native_tools=()),
        ToolSpec("regress_compare", "Decide accept/reject/inconclusive from stored base and candidate results, known failures and performance tolerance. "
                 "C4 /2 separates tests (pass/fail/incomplete) from verdict. Accept requires clean committed source identities on both sides. "
                 "Inconclusive means harness errors, wall-clock timeouts or no shared tests: rerun, do not accept. "
                 "Writes verdict.json beside the candidate unless out is given. Inputs accept directories, run IDs/prefixes or latest.",
                 schema({**COMPARE, "base": S, "candidate": S, "out": S}, ["base", "candidate"]), _call("compare"), side_effects='writes verdict to out or candidate directory', native_tools=()),
        ToolSpec("regress_gate", "Gate a change by running a tier on base/candidate revisions or comparing stored runs. "
                 "base and base_rev are mutually exclusive; cand and cand_rev are mutually exclusive. "
                 "Use base_rev or base; candidate defaults to HEAD when clean. Dirty trees run but cannot accept: "
                 "C4 /2 reports tests separately and not_accepted_reason=uncommitted. Commit (a scratch branch is fine) and rerun; complete RTL identities reuse passing results. Returns a job; the runner takes the core lock.",
                 schema({**COMPARE, **RUN, **BUDGET, "tier": {**S, "default": "quick"}, "config": S,
                         "base_rev": S, "base": S, "cand_rev": S, "cand": S, "out": S}),
                 handler("rvw.regress.cli", "gate"), long=True, side_effects='long-running; launches project native adapter and revision builds; writes run artifacts and history under project output', native_tools=()),
        ToolSpec("regress_history", "Find stored runs and their status before comparing or resuming; filter core, revision prefix or tier.",
                 schema({**CORE, "rev": S, "tier": S, "limit": {**I, "default": 20, "minimum": 0}}),
                 _call("history"), annotations=RO, side_effects='read-only', native_tools=()),
        ToolSpec("regress_known_list", "Inspect recorded known failures before triage or gating; choose file or core config.",
                 schema({**CORE, "file": S}), _call("known_list"), annotations=RO, side_effects='read-only', native_tools=()),
        ToolSpec("regress_known_add", "Record an understood failure with a reason. Give suite/id/signature, or from_ for failures in stored results. "
                 "Indexed imports are scoped by core; explicit result paths must also match that core. "
                 "Imports keep result configs; config filters results. from_ and signature are mutually exclusive. "
                 "Updates the known-failures TOML selected by file or core.",
                 schema({**CORE, "file": S, "from_": S, "suite": S, "id": S, "signature": S,
                         "config": S, "reason": S, "rev": S}, ["reason"]), _call("known_add"), side_effects='writes the selected known-failures file', native_tools=()),
        ToolSpec("regress_known_remove", "Remove a resolved or obsolete known-failure entry by suite and test ID, optionally signature.",
                 schema({**CORE, "file": S, "suite": S, "id": S, "signature": S}, ["suite", "id"]), _call("known_remove"), side_effects='writes the selected known-failures file', native_tools=()),
    ]
