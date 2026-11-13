# C7. MCP tools (`rvw mcp`)

`rvw mcp` is one stdio MCP server for every rvw tool. Each subpackage plugs in without editing
the server:

- Add `rvw/src/rvw/<tool>/mcp_tools.py` with a function `mcp_tools()` returning a list of
  `rvw.mcp.ToolSpec`. Discovery imports `rvw.<pkg>.mcp_tools` for every subpackage, as `rvw`
  imports `rvw.<pkg>.cli`. A package whose import fails is skipped with a message on stderr.
  Modules outside rvw can be added with `RVW_MCP_PLUGINS=module[,module]`.
- `ToolSpec(name, description, input_schema, handler, long=False, annotations={}, isolate=False)`:
  - `name` is `<tool>_<verb>` (`query_drivers`, `regress_run`, `bundle_make`), unique;
  - `description` tells an agent when to use it;
  - `input_schema` is a JSON Schema object (`rvw.mcp.schema(properties, required)` helps);
  - `handler(**arguments)` returns a JSON-serialisable value, normally the same dict the CLI
    prints with `--json`, so CLI and MCP never disagree. Raise `rvw.mcp.ToolError(message, data)`
    for expected failures; the agent gets `{"error": message, **data}` with `isError`.
  - `annotations`: MCP tool annotations, e.g. `{"readOnlyHint": True}` for queries.
- `mcp_tools.py` must not import the MCP SDK (only `rvw.mcp.spec`), so declaring tools works
  without the optional dependency and `rvw mcp --list` works everywhere.
- **Long jobs**: anything that can take more than a few seconds (builds, simulations,
  regressions, bundles) sets `long=True`. The server runs it in a worker thread and returns
  `{"job_id": ...}` at once. If the handler has a `job` parameter it receives a
  `rvw.mcp.jobs.Job`: `job.log(line)`, `job.set_progress(text)`, `job.run(cmd, cwd, env)` (runs a
  subprocess, streams its output into the log, kills it on cancel), `job.check()` /
  `job.cancelled`. Built-in tools follow jobs: `job_status(job_id, wait_s)` (status, result when
  done; `wait_s` up to 60 blocks until it finishes), `job_log(job_id, tail)`,
  `job_cancel(job_id)`, `job_list()`. Heavy jobs still take the `boom` lock themselves
  (`rvw.mcp.worker.handler(..., lock="boom")` or the adapter's `with-lock.sh`).
- **Cancel**: `job_cancel` sends SIGTERM to the process group of every subprocess the job
  started with `job.run`, SIGKILL to what is left after 15 s (`Job.GRACE_S`, longer than the
  5 s `rvw.common.proc.GRACE_S` a worker gives its own adapter or solver groups), and reaps them.
  It returns `cancelled` once the job has ended, or `cancelling` while a handler that runs Python
  in the server has not reached `job.check()` yet. Processes that left the job's group (their
  own `start_new_session`) are stopped only by the handler's own cleanup (`rvw.common.proc`).
- **Job retention**: the server keeps the newest 100 finished jobs; `job_status` of an older one
  is an error that says it was evicted.
- **Isolated short tools**: `isolate=True` (or a name matching `RVW_MCP_ISOLATE`, default
  `wave_*`) runs a short tool's handler in a worker process. It answers inline if it ends within
  `RVW_MCP_SYNC_S` (20 s); otherwise the call returns `{"job_id": ...}` and continues as a
  cancellable job. The handler must be a module-level function.
- Results larger than 400 000 characters of JSON are shortened, not cut: the largest lists and
  strings are trimmed, the result keeps its shape (a non-object result is wrapped as
  `{"result": ...}`), and it gains `"truncated": true` and `"truncation": {note, original_chars,
  cuts: [{path, total, kept}]}`. It is always valid JSON. Give tools `limit`, `depth` or `scope`
  arguments instead of relying on that.
- Test a package's tools through `rvw.mcp.registry.Registry([...]).call_json(name, args)`, and
  end to end with an MCP client over stdio as `rvw/tests/test_mcp.py` does.

## Authenticated remote MCP transport

MCP SSE requires bearer authentication on both session and message endpoints.
Each token has an explicit tool allowlist, fixed project and separate job store.
Clients can inspect and cancel only their own jobs. Remote calls use owned workers
and optional per-client per-run supervisor budgets. Disconnect does not cancel;
server shutdown does. Read-only roles are limited to the implemented query list.
No new verification verdict or hostile-input guarantee follows from transport.

## Interface audit declarations

ToolSpec adds optional side_effects (read-only or writes-files), native_tools
(tuple of inventory ids, empty when none), and result_envelope fields.
Unknown declarations remain null and produce audit findings. Long-running is
declared separately with long=True. The static audit checks schemas and Python
signatures without executing handlers. Existing argument names remain valid.

## Tool profiles

Profiles filter the loaded tools without renaming them. The all profile is the
default. Core, job, search and describe tools remain available. Workflow filters
use the agent playbook. Search returns purpose and profile; describe returns the
input schema and declarations. Remote discovery cannot widen client allowlists.

## Common result envelope

MCP transport results add status, summary, artifacts, next and diagnostics.
An explicit evidence verdict uses pass, fail, inconclusive, no_checks,
unsupported, not_installed or error. Completion alone has no verdict.
Legacy result fields remain at the top level. Non-object results use result.
An older verdict outside this vocabulary moves to legacy_verdict and the common
verdict is inconclusive. This does not change C4 CLI decisions or exit codes.
The Python Registry.call API retains raw results. Registry.call_json and MCP
apply the envelope. Artifacts and suggested next calls are empty if unknown.


## Common error form

Errors retain error text and add code, hint and diagnostics. Codes include
unknown_tool, invalid_arguments, invalid_input, not_installed, tool_error and
internal_error. Missing inventory executables or modules use not_installed and
the inventory's exact scripts/install.sh flag. Missing input files are input
errors. ToolError accepts an explicit code and native_tool in its data.
Unidentified dependencies point to rvw doctor; no install flag is guessed.

## Unified job controls

Start any long tool to get a job_id. Use job_status or job_events to follow it.
Use job_result to fetch its current state and final result. Use job_cancel to
stop it. Existing job_log and job_list names remain valid. Job ids are scoped
to the server session. Worker execution retains process-group cancellation.
Previously inline sim_checkpoint, sim_resume, sim_suffix_check, csim_convert
and soc_audit now use jobs. Small metadata tools remain inline.


## CLI discovery and JSON fallback

Every CLI parser accepts --json and shows a generated example in --help.
Commands with native JSON output keep their contract schemas and exit codes.
Other commands wrap their text in output with the common envelope. Exit 3
stays inconclusive. Exceptions use the common error object and exit 2.
Exit 0 means command completion; it does not create a verification pass.
rvw mcp command-map --json generates command paths and workflow steps from
the actual parsers and agent playbook. It is not a second command registry.

## Schema help and discovery smoke

rvw mcp describe NAME returns a tool's full schema and declarations.
rvw mcp call NAME --dry-run --arguments '{}' validates supplied values but
does not require missing arguments. It returns help data and dry_run: true.
It never calls a handler or starts a job. This is not verification evidence.
rvw mcp smoke checks every loaded tool through that path. Discovery problems
or schema-help errors return exit 2. Fast tests forbid handler and job dispatch.

## Isolation of wrapped providers

A packaged isolated handler that cannot be imported directly is resolved by
its discovered tool name in the worker. Wrappers retain their actual call
signature, including indexed wave arguments. The sync window, job controls
and process cancellation rules are the same as for directly importable tools.

## Argument aliases

Canonical database arguments use `db`. The farm dashboard filter uses `run_id`.
The old names `db_path` and `run` remain accepted on those tools. Their schema
properties carry `deprecated: true` and `x-alias-for` with the canonical name.
A call must supply at most one name for each value. Required inputs accept either
name. A boolean `run` selects execution and is not a run directory alias.

## Native dependency declarations

`native_tools` lists optional dependencies by installer inventory ID. Executable
names are not inventory IDs. A tool with no optional inventory dependency uses
an empty tuple. Its effect description must still name system commands such as
Git and SSH, and project-selected commands. Keep the native declaration unknown
when an optional dependency has no inventory entry. Do not hide that gap with an
empty tuple.

## Native tool inventory gaps

Every discovered tool declares its effects beside its registration.
Three dependencies have no optional installer inventory ID:

- `arch_sched_study` can launch llvm-mca.
- `cov_mutate` can launch MCY.
- `farm_batch` can launch kubectl.

These tools retain unknown `native_tools` metadata and one audit finding each.
Their effects name the missing dependency.
An empty tuple must not hide an unknown dependency.
Git is a base installer prerequisite. Replay tools name Git in their effects.
The audit baseline contains only these three findings.
The fast inventory test checks this boundary and the replay/SVA discovery paths.
