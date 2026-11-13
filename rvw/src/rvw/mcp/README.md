# rvw mcp

One MCP server (stdio) that gives an agent every rvw tool. Tools come from the rvw subpackages
themselves, so a new tool needs no change here (contract C7 in `docs/PLATFORM_CONTRACTS.md`).

```sh
cd rvw && uv pip install -e '.[mcp]'      # the mcp SDK, 1.x or 2.x
rvw mcp --list                             # the tools (works without the SDK)
RVW_DESIGNDB=$PWD/../SpinalDB/out/boom-small.db rvw mcp     # serve over stdio
```

Client configuration (Claude Code `.mcp.json`, other clients alike):

```json
{"mcpServers": {"rvw": {"command": "/abs/path/rvw/.venv/bin/rvw", "args": ["mcp"],
                        "env": {"RVW_DESIGNDB": "/abs/path/SpinalDB/out/boom-small.db"}}}}
```

Tools include all `query_*` commands, `regress_list/run/compare/gate/history`,
`regress_known_list/add/remove`, `cosim_check/generate`, `cov_merge/report/rank/select/functional/prove/mutate`,
and `perf_report/compare`. Slashes abbreviate individual tool names, e.g. `cov_merge` and `cov_report`.
The job tools are `job_status`, `job_log`, `job_cancel`, `job_list`.
Options: `--only query,regress` serves only selected packages;
`RVW_MCP_PLUGINS=my.module` adds modules outside rvw.

Regression run/gate, both cosim tools, every coverage tool and both performance tools return
jobs. Their final result is the same JSON produced by the CLI's shared Python functions.
`worker.py` calls those functions in a private process through `job.run`, streams progress to
job_log and transfers the result through a temporary JSON file. `job_cancel` sends SIGTERM to the
job's process group and SIGKILL after `Job.GRACE_S` (15 s), then reaps it; the worker unwinds
regression locks and kills separate adapter/solver groups on SIGTERM (their own grace is
`rvw.common.proc.GRACE_S`, 5 s, so the worker finishes before the job's SIGKILL). When a job's
process exits by itself, `job.run` SIGKILLs what is left of its group (background members) before
it returns, as `rvw.common.proc.run_group` does. Regression owns its configured resource lock;
coverage proof/mutation workers start through `python -m rvw.common.lock boom` (the
`with-lock.sh` lock). `wave_*` tools run in a worker process too: they answer inline within
`RVW_MCP_SYNC_S` (20 s), else return a cancellable job. The server keeps the newest 100 finished
jobs. Results over 400 000 characters are shortened to valid JSON with `"truncated": true`.

See each package's README for arguments, read-only operations and output artifacts. No MCP SDK
is imported by tool declarations or workers. `rvw mcp --list --json` works without the SDK.

## Adding tools from a package

```python
# rvw/src/rvw/<tool>/mcp_tools.py  (no MCP SDK import here)
from rvw.mcp.spec import ToolError, ToolSpec, schema

def _status(run_dir: str) -> dict:
    return load_result(run_dir)                      # the same dict `rvw <tool> status --json` prints

def _run(suite: str, config: str = "small", job=None) -> dict:
    rc = job.run(["rvw", "regress", "run", suite, "--config", config, "--json"])   # streamed to job_log, killed on cancel
    if rc:
        raise ToolError(f"exit code {rc}")
    return {"ok": True}

def mcp_tools():
    return [
        ToolSpec("tool_status", "What a run directory holds ...", schema({"run_dir": {"type": "string"}}, ["run_dir"]), _status,
                 annotations={"readOnlyHint": True}),
        ToolSpec("tool_run", "Run a suite (minutes) ...", schema({"suite": {"type": "string"}, "config": {"type": "string"}}, ["suite"]),
                 _run, long=True),
    ]
```

A `long` tool returns `{"job_id": ...}` at once; the agent calls `job_status(job_id, wait_s=60)`
until `status` is `done` (result included), `failed` (error and log tail) or `cancelled`.
Errors: raise `ToolError(message, data)`; the agent gets `{"error": ..., **data}` with `isError`.

## Code

`spec.py` (`ToolSpec`, `ToolError`, `schema`; no SDK), `jobs.py` (`JobManager`, `Job`),
`registry.py` (discovery, dispatch, the job tools, JSON results; no SDK), `worker.py` (shared
Python calls in cancellable processes), `server.py` (the SDK
glue, 1.x decorators or 2.x constructor handlers), `cli.py`. Tests: `rvw/tests/test_mcp.py` runs
the registry directly and a real client session over stdio (including a plugin's long job).

## Decisions

- Start workers with `sys.executable -m rvw.mcp.worker`. This preserves the installed
  Python environment and `PYTHONPATH`. The private request and result files carry the
  server's own arguments and envelope. Tool handlers capture their verdict inputs.
- Use `worker.handler` for fixed-action and action-free `execute_json` calls. Coverage
  proof and mutation select a lock per call: explicit `lock`, then `$RVW_HEAVY_LOCK`,
  then `boom`. An empty string disables that lock. Keep query leases and formal evidence
  checks in their tool layers.
- Validate JSON Schema before dispatch. Refuse unknown arguments, invalid types, bounds,
  enum values, NaN and Infinity. Do not coerce values or insert schema defaults.
- Require both a successful worker exit and a valid result envelope. Missing output,
  worker errors and cancellation cannot return a successful result.
- `Job.run` owns cancellation, process registration and SIGKILL escalation after 15 s.
  Workers unwind their separate adapter groups before this limit. Report `cancelled`
  only after group cleanup and reaping. Stop background group members after leader exit.
- Keep plugin discovery and `RVW_MCP_ISOLATE` (default `wave_*`). Isolated calls answer
  inline within 20 s or become cancellable jobs. They use a separate thread pool.
- Truncation keeps valid JSON, result shape, retained summaries and explicit cut paths.
  Keep support for MCP SDK 1.x and 2.x. Tool declarations do not import the SDK.

Native worker budgets use `RVW_JOB_BUDGET`. See [common](../common/README.md#native-job-budgets).
A budget stop fails the worker call and retains its cost report in job status.

See the complete [CLI and MCP reference](../../../../docs/COMMAND_REFERENCE.md) for command paths,
options and built-in tool arguments. The reference is checked against the code.

## Authenticated remote MCP

`rvw mcp --transport sse --clients clients.json --host 127.0.0.1 --port 8766`
serves MCP over HTTP/SSE. Connect to `/sse` with `Authorization: Bearer TOKEN`.
The SDK advertises `/messages` for client messages. Both endpoints require the
same token. Each token owns its transport sessions, registry and job manager.
Another client cannot read, list or cancel its jobs. Disconnecting SSE does not
cancel a job. Reconnect with the same token to inspect it. Server shutdown stops
owned jobs. Process-owned locks and cancellation retain their existing behavior.

The JSON file maps secret tokens to policy objects, for example:

```json
{"replace-with-a-secret":{"tools":["evidence_query"],"read_only":true,
 "project":"/path/rvw.toml","budget":{"wall_seconds":60,"job_count":5}}}
```

Every policy needs an explicit tool allowlist. Unknown tools are refused.
`read_only: true` permits only the implemented read-only query role:
`query_drivers`, `query_loads`, `query_path`, `query_where`, `evidence_query`.
Job status/log/list/cancel remain available for that client's own calls.
Project selection is fixed by policy; calls cannot override it with project or
core. This is a trusted-project service, not a filesystem sandbox.

All allowed remote tools run as background jobs in owned workers, including
short queries. Their calls return job IDs. `budget` uses the existing supervisor's
CPU-seconds, wall-seconds and launch-count units for each run. The policy applies
without changing another client's environment. Cost reports remain in job status.
Budget exhaustion is an error or inconclusive result, never accept. Unimportable
third-party handlers are refused. Client totals across multiple runs are not
cumulative budgets; use farm queue project budgets for that scheduling model.

Install the `mcp` extra, including uvicorn. Bind locally and put TLS at an
existing reverse proxy for remote clients. The SDK retains its transport host
checks. Tokens grant trusted tool access. There are no token expiry, arbitrary
read-only roles, durable remote MCP job stores or hostile-input guarantees.
Tests cover a local HTTP/SSE protocol roundtrip, auth, ownership and budgeted
worker errors. No cloud agent or external proxy was tested.

## Interface audit

Use `rvw mcp audit --json` for a static report of every tool. It checks names,
descriptions, schema fields, common argument aliases, handler signatures and
declared effects and native dependencies. It does not call handlers. Unknown
metadata stays unknown. The fast baseline test permits recorded debt but rejects
new findings. Use `project`, `out`, `run_dir`, `elf`, `trace`, `db`,
`config`, `seed` and `json` for these concepts in new interfaces.

## Load a profile

Use `rvw mcp --profile core|verification|formal|arch|debug|soc|all`.
The default is `all`. Each profile includes core tools and job tools.
Use `--workflow test-fails` to select the exact playbook tools and core tools.
The profile and workflow filters intersect when both are set.
`rvw_tools_search(keyword)` searches the available catalog.
`rvw_tools_describe(name)` returns arguments, effects and profile.
Search can describe tools outside the loaded profile. Restart with that profile
to call them. Remote catalogs contain only tools from the client's allowlist.

## Common results

MCP results add `status`, `summary`, `artifacts`, `next` and `diagnostics`.
A verdict is present only when the source result has one or an explicit evidence
status. Completion is not a pass. Existing result fields remain available.
Older verdict terms remain in `legacy_verdict` with a common verdict of
`inconclusive`. Direct Python `Registry.call` retains its raw return value.


## Errors

Read `code` and `hint` on errors. `not_installed` includes the exact installer
flag when the missing tool matches the shared inventory. A missing input file
is an input error. Providers can raise `ToolError(message, data, code=...)`.
Set `native_tool` in data to an inventory name when reporting missing tools.

## Job protocol and blocking inventory

Start a tool marked `long` in `rvw mcp --list --json`. It returns `job_id`.
Call `job_status(job_id, wait_s=60)` or `job_events(job_id)`.
Call `job_result(job_id)` for the final result. Call `job_cancel(job_id)`
to cancel. Existing `job_log` and `job_list` remain available.

These formerly inline tools now run in owned worker processes:
`sim_checkpoint`, `sim_resume`, `sim_suffix_check`, `csim_convert` and
`soc_audit`. The first two can execute native operations. The others can scan
large traces or databases. Long providers that accept no job context also use owned workers. This includes
agent benchmark runs, security campaigns, reverse stepping, UVM native flows
and the wave benchmark. Providers with job context retain their handlers.
Other inline tools are file reports, generators or metadata calls. A provider
must still set `long=True` if its runtime can grow beyond a few seconds.


## CLI command map

Use `rvw mcp command-map --json` to get the current parser inventory and the
ordered commands in each agent workflow. Use `rvw <tool> --help` for options
and a generated example. Every parser accepts `--json`.
Existing JSON handlers keep their contracts. Commands without a JSON handler
return their text in `output` with the common envelope. Exit codes remain
those of the command. Unhandled JSON-mode exceptions return a common error
and exit 2. Exit 0 alone never creates a pass verdict.
