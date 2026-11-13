# Native regression farm

This increment supplies `rvw farm run`, `farm_run` over MCP, and
`rvw farm dashboard`. It uses native SSH, Python and the installed core adapter.
It does not choose a container policy. #59 remains an owner decision.

## Run

Install the same workstation and native tool builds on each worker. Configure
SSH login keys and trusted host keys. Obtain the local adapter's complete
`rvw.adapter-capture/2` identity document. Its result claims must include the
native build identity and a clean harness. Supply the identity command as an
argument array. Each worker must return the exact same identity document.
Different paths or tool identities can therefore refuse execution.

Write a JSON host array:

```json
[{"name":"worker-a","address":"host-a","python":"/opt/rvw/bin/python"},
 {"name":"worker-b","address":"host-b","python":"/opt/rvw/bin/python"}]
```

A host can set `ssh_options` to an array of native SSH options.
Prepare a C1 run-many JSONL manifest with explicit config and seed values.
The ELF is transferred by value. Other declared stimulus inputs must already
exist on the workers with the identity the adapter records.

```sh
rvw farm run --hosts hosts.json --manifest manifest.jsonl \
  --adapter '["/path/run.sh"]' \
  --identity-command '["/path/run.sh","identity","--config","small"]' \
  --identity identity.json --out /tmp/campaign --jobs 2 --timeout 600
rvw farm dashboard --root "$HOME/.cache/rvw/results" --out /tmp/dashboard.html
```

The output directory must be new. Rows get stable campaign-local IDs. The report
retains every expected cell, its options, ELF hash, shard results and missing IDs.
It preserves returned shard artifacts and checks their hashes. Each C1 result
must match its ELF hash, config, seed and all identity claims. A lost host,
identity mismatch, aborted shard or missing result makes the campaign
inconclusive (exit 3). A complete campaign can contain DUT failures. Exit 0 means
collection is complete. It does not mean pass or gate accept.

Use `rvw farm cancel --out /tmp/campaign` or MCP `farm_cancel` with `out` to
cancel a campaign. Each shard has a random control token. A separate SSH request
signals its worker. The worker unwinds `run_group`, stops all owned process
groups, and stores an acknowledgement on the host. The cancel endpoint uses
`ps` on the host to confirm that those groups have no live members. Zombies do
not count as live members. A lost host or missing acknowledgement is inconclusive.
`control.json` and `cancellation.json` retain the requests and replies. Keep the
campaign directory until cancellation finishes. This endpoint also works from
a later command after the dispatch process stops.

A host can set `resources`, for example:

```json
{"cpu": 2, "memory_bytes": 4294967296, "locks": ["native-build"]}
```

CPU slots must cover `--jobs`. Workers reserve these values under one host file
lock before they run the identity command or adapter. All aliases for the same
OS user share capacity. Different OS users do not share this reservation store. Set `~/.config/rvw/farm-capacity.json` on each host to an object
with `cpu` and `memory_bytes`. Defaults reserve at most logical CPU count minus
one (minimum one), and half physical memory. Omitted memory means zero requested
bytes. Omitted locks means no named lock. A request waits up to the shard timeout
for capacity. Requests use a persistent first-in, first-out queue per OS user.
Small requests cannot bypass an older large request. This can leave slots idle
while that request waits. Timed-out tickets and dead waiting processes leave the
queue. Dead active reservations still need checked cleanup. The reply records reserved values and `queued_s`. Each request owns
its reservation. Normal completion, timeout and handled cancel release it.
These are cooperative reservations. They do not cap actual RSS or CPU use.
Adapters and unrelated processes can exceed them. Dead worker records require
owner cleanup after process groups are checked. No capacity is reclaimed blindly.

The dashboard reads C3, C4 and history. Missing evidence is inconclusive. It
shows per-status counts and plots recorded C3 `ipc` and `coverage` metrics by
core, suite and config. It also plots pass rate (conclusive passes divided by
all recorded tests) and run time (sum of all test `wall_s` values). Missing wall
times prevent a run-time sample. Charts and tables use oldest-first history and
retain gaps. Missing samples are not zero. It does not merge bins or
establish coverage compatibility or verification closure.

## Notification export and access

`rvw farm notifications --out /tmp/campaign` (MCP `farm_notifications`) emits
`rvw.farm-notifications/1` JSON. Events separate DUT failures, infrastructure
faults, incomplete shards and collection status. Event IDs are deterministic
for the same captured event. Consumers can use them to suppress duplicate
notifications. The command reads checkpoints after a controller crash. It does
not send messages, store delivery state or retry external services. External
email, chat and webhook delivery remain open. Collection complete is not pass.

SSH access uses OS accounts and trusted keys. Capacity files are per OS user.
The static dashboard has no server, login, roles or write API. Use OS file
permissions or an existing authenticated web host to share its HTML. Do not
assume that separate SSH users share capacity or that generated HTML supplies
access control. A shared multi-user scheduler and authenticated dashboard
service remain open.

## Recorded repeats

`rvw farm classify campaign-a/farm.json campaign-b/farm.json` (MCP
`farm_classify`) compares recorded executions. It does not launch retries.
New campaign reports capture a campaign ID and the full tool identity. Groups
bind that identity, the ELF hash and all options, including config and seed.
Different seeds or builds stay separate. Reports without these captured
identities and duplicate executions are refused.

Each `rvw.farm-classification/1` group retains every original outcome, report
path, report hash, campaign ID and cell ID. A conclusive DUT failure followed by
a pass sets `unstable: true` and keeps status `fail`. Errors and inconclusive
outcomes set `infrastructure_fault` separately. Missing attempts stay explicit.
No outcome is waived. This classification does not earn C4 acceptance.
Automatic retry selection and declared retry execution policies remain open.

## Filter history

`farm dashboard` accepts `--core`, `--suite`, `--config`, `--gate` and `--run`.
The first four use exact values. `--run` matches a run-ID substring. The same
filters are available through MCP `farm_dashboard`. Counts and trends use only
selected suites. Missing evidence stays visible if its suite or config cannot
be checked. The HTML records the active filters. Gate filters select the recorded
C4 verdict, not a verdict inferred from C3 pass counts.

## Native OS limits

A host can set `limits`, for example `{"cpu_seconds": 120,
"file_bytes": 1073741824, "open_files": 256}`. Linux also supports
`address_space_bytes`. Other OSes refuse that field. Unknown fields, nonpositive
values and unsupported limits are errors before identity or adapter execution.
The worker applies hard `setrlimit` limits in a fresh Python process, then calls
`exec`. Identity commands, adapters and their children inherit these limits.
An existing lower OS hard limit takes precedence. Values apply per process,
not to the campaign total. CPU time is not a CPU slot count. Address space is
not RSS. Exceeding a limit cannot earn collection completeness from missing C1
files. Limits are opt-in and do not replace cooperative host reservations.

## Controller recovery

`rvw farm recover --out /tmp/campaign` (MCP `farm_recover`) reads the saved
plan and shard checkpoints. The controller saves the plan before dispatch and
checkpoints each validated C1 cell. Recovery preserves failures and lists missing
cells. Without `farm.json`, the campaign stays inconclusive even if every shard
has a checkpoint. Recovery does not rerun jobs, modify evidence or claim worker
cleanup. Use `farm cancel` to check cleanup. A SIGKILL between receiving an
artifact and validating its C1 can leave that cell missing in the checkpoint.

## Decisions and limits

- Workers own temporary directories and bounded process groups. Normal completion
  removes temporary data. SIGTERM and SIGHUP unwind group cleanup. SSH loss can
  leave the worker running until its declared timeout. Use the separate cancel
  endpoint to request acknowledged cleanup. Crash recovery remains open. SIGKILL
  can leave temporary data, control records and capacity reservations.
- Every run checks tool identity. This is a C1 execution interface, separate from
  `regress gate`. C8 cache admission and gate verdicts stay in the existing runner.
  Farm artifacts are not automatically imported as accepted C3 generations.
- The protocol buffers JSON and base64 artifacts in memory. Large waveform
  streaming, automatic discovery and campaign-scale performance work remain open.
- Requirements closure, retries, failure review, coverage-plan revisions, external
  review exports and licensed-tool scheduling remain open under #25.
- Test native SSH with two localhost entries. Set `RVW_TEST_SSH_OPTIONS` to a JSON
  option array for a test server. Run `pytest rvw/tests/test_native_farm.py`.
  These are protocol fixtures. They are not RTL verification results.

Collection checks explicitly requested `max_cycles` and `mem_latency` in each C1 result.
Missing or different values make collection inconclusive.

### Disk and project reservations

Host capacity also accepts `disk_bytes`, `jobs`, and `projects`.
`projects` maps project names to limits for `cpu`, `memory_bytes`, `disk_bytes`
and `jobs`. Missing project limits use the host limit. When this map is nonempty,
every request must name a configured `project`. Each project's simultaneous
requests share its limits, even through different host aliases.

Request `resources` can set the same four quantities and `project`. Disk and
memory default to zero; CPU and jobs default to one. Old host files default
disk capacity to half the free bytes and jobs to CPU capacity. The scheduler
also checks current free disk before admission. Reports include effective
`limits`, `queued_s`, `held_s`, `released` and `outcome`. Handled cancellation
releases every quantity. Requests above a host or project limit are refused.
Capacity conflicts wait up to the request timeout.

These are declared simultaneous reservations, not measured RSS, disk writes,
CPU quotas or cumulative project usage. A caller that declares zero memory or
disk reserves none. Direct third-party subprocesses do not acquire these limits.
Crash recovery still needs owner cleanup. Money rates and measured build and
simulation categories remain open under #57.

The dashboard also plots recorded C3 `sim_khz` and
`sim_instructions_per_s` per core, suite and preset. Missing values stay absent.
The denominator includes adapter execution and artifact handling. It excludes
model setup. These plots do not establish equivalent results or speedups.

## Persistent service queue

Use `rvw farm queue --root DIR --operation submit --options
'{"owner":"alice","command":["/path/adapter"],"priority":2,"retries":1}'`.
Run `--operation work` once per available local execution slot. Run it again
until the queue is empty. Queue records and attempts survive controller restarts.
Higher priority runs first. Equal priorities choose the owner with fewer recorded
attempts, then the oldest job. This is attempt fairness, not CPU-time fairness.
Retries cover command errors, timeouts and infrastructure errors. Every attempt
stays recorded. An exit code of zero means collection complete, not DUT pass.
Use `farm classify` on C1 campaign reports for identity-bound DUT instability.

Use `--operation recover` after worker death. Live controllers retain ownership.
A dead worker's recorded process group is killed only if its leader start time
still matches. A live group with an unknown identity requires operator cleanup.
Recovered work retries only under its declared retry count. Otherwise it stays
inconclusive. A running cancel stays `cancel_requested` until group cleanup ends.
This queue does not change the existing SSH executor recovery protocol.

`rvw farm serve --root DIR --tokens tokens.json` serves a live run view and
HTTP API on localhost port 8765. The token file maps bearer tokens to owners.
`GET /runs`, `POST /runs` and `POST /cancel/ID` enforce owner isolation. The root
page keeps the token in page memory. Workers must be launched separately with
`farm queue --operation work`. Only trusted project users can submit commands.
Use a TLS reverse proxy for remote access. The API does not supply a sandbox.
MCP `farm_queue` exposes the same local operations. C3 trends remain available
through `farm dashboard`. Cluster drill-down is not yet part of the HTTP view.

## Local and Kubernetes batch jobs

`rvw farm batch --plan plan.json --action render` emits a Kubernetes Job List.
Each shard becomes one Job with zero hidden Kubernetes retries. A plan sets
`name`, `image`, `shards`, optional `namespace`, `timeout`, `resources`, and PVC
`volumes`. Each shard sets a `command` argument array and explicit `results`:
`[{"path":"cell/result.json","contract":"C1","identity":{"elf_sha256":"..."}}]`.
C3 files use `contract: "C3"`. Identity keys can name nested C1 fields.
Volumes set `claim`, `mount` and optional `read_only`. Use a read-only model
cache and a separate writable results PVC. Mount the same paths on collectors.
Tool images, hashed inputs and model builds are supplied by the project.

Use `--action submit --executor k8s`. Save the returned IDs. Pass them as JSON
with `--ids` to `status` or `cancel`. Status returns Kubernetes Job conditions;
an absent condition is not success. Cancellation waits for foreground deletion.
`--executor local --root DIR` queues the same commands in the persistent local
service. Run local workers with `farm queue --operation work --root DIR`.
`--action collect --root SHARED_RESULTS` validates every expected C1/C3 file.
Missing, invalid or inconclusive results remain inconclusive. Complete collection
can include DUT failures. MCP exposes these operations as `farm_batch`.

The rendered JSON is a plain Kubernetes manifest. Tests validate its structure
and exercise a fake kubectl. No cluster or kind execution has run. This does not
supply tool images, object storage, automatic cache builds, C3 gate publication,
`regress gate --executor`, or a scale/parity result. Each command and its result
paths must be supplied in the shard plan. Existing SSH plans remain unchanged.

## Cumulative service budgets

`rvw farm budget --root DIR --scope project:demo --limits
'{"core_hours":2,"wall_seconds":3600,"jobs":100}'` sets a persistent budget.
Scopes are `run:JOB_ID`, `agent:OWNER`, and `project:NAME`. Queue submissions
can set `project` and positive `cores` in their options. The default project is
`default`, with one declared core. All configured scopes apply. Active attempts
reserve their maximum remaining charge under the queue transaction. Shared
project and agent limits therefore include simultaneous workers.

The worker reduces its timeout to the remaining wall/core-hour budget. Exhaustion
cannot earn a DUT pass. Every launch and retry consumes one job. Cleanup time is
charged, including any overrun beyond the timeout. The report groups charges by
execution state and retains every attempt. It does not infer a DUT verdict from
process status. `--rate-per-core-hour` sets an explicit money rate in caller units.
Without a rate, cost is null. MCP `farm_budget` has the same interface.

These budgets govern the local service queue. CPU is declared cores times wall
time, not measured CPU or an OS quota. Memory/disk reservations remain in the SSH
host scheduler. Kubernetes admission and external plugin accounting are separate.

## Automatic failure triage

`rvw farm triage --root RUN --baseline BASE --known known.toml --bundles OUT`
reads recorded C3 results. It groups failures by core, configuration, category
and signature. It reuses assertion identity checks. Recorded
`details.first_mismatch.pc` and `instruction`, or `details.trap_cause`, refine
signatures when available. Infrastructure and incomplete evidence stay separate.
Every member retains its test, seed, run path and source revision. Known-failure
matches are links for review, not waivers. Revisions and an optional baseline
identify the recorded comparison range.

`--bundles` calls the existing C5 builder once per cluster with a recorded run.
It disables reruns and SpinalTrace execution. Missing run paths and bundle errors
stay explicit. `--baseline` reuses the identity-aware C3/C4 comparison for new
failures, fixes, missing tests and changed inputs. MCP exposes `farm_triage`.
This report does not infer a root cause or accept a change from cluster counts.

## Time-budgeted impact suites

`rvw farm select --db design.sqlite --changed '["src/Unit.scala"]'
--catalogue observations.json --seconds 600` proposes tests for ten minutes.
The catalogue supplies `database_sha256` and `tests`. Each test has a unique
`id`, measured positive `wall_seconds`, observed signal paths in `signals`, and
optional `mandatory: true`. The source paths must match the database's files.
The selector follows downstream design-database edges from changed components
and signals. It ranks tests by new impacted signals per second.

Use the existing `rvw cov select` for line-coverage impact selection. Its result
can be included as `coverage_selection`; `fallback_all: true` stays mandatory.
Missing signal observations, unknown files, empty impact maps or a changed
database hash retain all affected unknown tests, even beyond the time budget.
The report shows omitted tests, uncovered signals and any budget overrun.
This is an advisory scheduling plan. It does not replace a regression gate.
Held-out regression validation has NOT RUN. MCP exposes `farm_select`.

## Agent workflow plans and events

`rvw farm workflow --root DIR --action create --plan plan.json --owner alice`
stores a dependency plan. A plan has `nodes`, each with `id`, a `command` array,
optional `needs` node IDs, `timeout` and `retries`. Optional `project` selects a
queue budget scope. Unknown dependencies and cycles are refused. Save the
returned workflow ID. Use `--action advance --workflow-id ID` to queue ready
nodes. Run queue workers, then advance again. Repeated advances do not resubmit
recorded nodes. `--action status` shows exact dependency and execution state.
Failed dependencies remain blocked. Execution complete is not verified pass.
`--action capabilities` returns tool names and argument schemas. MCP exposes
`farm_workflow`. This service does not create a separate top-level agent.

The authenticated HTTP service supplies `POST /workflows` with the same action,
plan and workflow_id fields. Owner comes from the bearer token. `GET /events`
replays only that owner's job and workflow events as SSE. Resume with
`Last-Event-ID` or `?after=SEQUENCE`. The finite replay closes after the captured
batch; reconnect for later events. No whole-result polling is needed. Sequence
IDs are persistent. Clients can discard duplicates. Completion is emitted when
a workflow is next advanced or inspected after its jobs finish. Webhook delivery
is not implemented. Use SSE or the local queue events API.
