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
  endpoint to request acknowledged cleanup. For new workers, it also checks dead
  worker process identities before cleanup and capacity release. Unverified old
  records need operator cleanup. SIGKILL can leave temporary artifact data.
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
through `farm dashboard`. The live HTTP view also exposes owner-scoped C3 history and C5 bundle drill-down.

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

## Live dashboard and checked SSH crash cleanup

The service root page now shows runs, recorded C3 pass-rate trends, failure
clusters, per-test history and C5 bundle buttons. `GET /snapshot` supplies the
owner-scoped view. `GET /bundle/JOB_ID?path=RELATIVE` reads only C5 summaries
within an owned job directory. Missing C3 evidence is no_checks. Missing trend
samples remain gaps. Commands must write C3 output under their job directory
for this view. Existing external history roots still use `farm dashboard`.
CLI `farm live --root DIR --owner NAME` and MCP `farm_live` read the same view.

Queue attempts now run in separate `JOB_ID/attempt-N` directories. Commands can
use `{attempt_dir}` to name that directory in an argument. All prior evidence
stays recorded. A valid C1 `result.json` records the DUT outcome separately from
command completion. Set `retry_on: ["dut_failure"]` with a retry bound for
explicit DUT retries. The default still retries only infrastructure/process
errors and timeouts. A later pass never erases an observed DUT failure. A mixed
pass/failure sets unstable only within a matching ELF, RTL, native tool and
option identity. Unknown identity cannot establish flakiness.

New SSH worker control records capture process start identities. After worker
death, `farm cancel` kills only checked owned groups, verifies no live members,
then releases that dead worker's capacity records. A reused PID or an unknown
live group is not reclaimed. Old records without process identity need operator
cleanup. Temporary artifact directories and remote artifact reattachment remain
open. Tests use local fake worker records and real local process groups.

## Build a shared shard plan from C1 inputs

`rvw farm plan --manifest manifest.jsonl --adapter '["/tools/run.sh"]'
--root /shared/campaign --image toolset@sha256:DIGEST --claim results --shards 8`
writes a fresh campaign directory with hashed ELF copies, per-shard run-many
manifests and `plan.json`. Every input needs explicit config and seed. Expected
C1 cells bind the ELF hash and those options. `--identity` can add native tool,
RTL and source claims. Conflicting claims are refused. MCP exposes `farm_plan`.

Submit that same plan with `farm batch --plan /shared/campaign/plan.json` and
`--action submit --executor local` or `--executor k8s`. The PVC must expose the
campaign directory at the same absolute path. The adapter must exist in both
execution environments. Other adapter stimulus dependencies must be mounted
and captured by the project. Collect with `--action collect --root
/shared/campaign`. A local fake-adapter test executes both planned shards,
collects both C1 cells and renders their cluster Jobs. No cluster or native RTL
parity is claimed. Gate publication and automatic tool-image builds remain open.

### Costs by recorded verdict

`farm budget` reports each attempt's charge beside original C4 verdict links
when `verdict.json` exists under that attempt directory. It checks the C4 schema
and records the path and SHA-256 without rewriting the report. Each attempt is
charged once. Missing C4 is not_recorded. Invalid or multiple verdict files are
ambiguous; their charges are not assigned to an invented verdict. Each row also
retains execution state and optional declared `category`, for example build or
simulation. Recorded verdict grouping does not establish current acceptance.
Budget or cleanup failures remain visible beside the original C4 observation.

Budget admission skips exhausted owners so other projects can run. A job blocked
only by an active reservation stays queued until that reservation is released.

### Cluster collection state

For cluster collection, pass `--executor k8s --ids 'SAVED_IDS'` with
`--action collect`. Every planned Job ID must be present. The collector checks
current Kubernetes state as well as C1/C3 files. Missing IDs, failed/incomplete
Jobs or a kubectl error make collection inconclusive while retaining artifacts.
A Complete condition and successful pod count are required for each Job.
An empty expected-cell plan is refused. Complete collection still is not DUT
pass or C4 acceptance.

All long farm and evidence-index MCP calls now use the shared owned worker
process path. Job cancellation and supervisor budgets apply to those calls in
stdio as well as remote MCP. The local queue still records its own attempt and
recovery state if its MCP worker stops.

When both sides record full commit IDs, each triage cluster includes explicit
`BASE..CANDIDATE` commit ranges. Unknown or short revisions do not create a
range. Regression diffs still require matching test input identities; a range
alone cannot establish a new failure or a fix.

A rendered Job also passed offline validation against the Kubernetes v1.34.0
OpenAPI Job schema at commit `f28b4c9efbca5c5c0af716d9f2d5702667ee8a45`.
The schema SHA-256 was
`d3b0cdc2fda15c753206d25ab459dc7c12df64e2fd652b6809687471ea751c37`.
This check included result/cache PVC mounts and resource requests. Cluster
admission, PVC binding and pod execution have NOT RUN.

## Native persistent local shards

`examples/regression-scale/submit.py` submits an explicit C1 manifest as one to
three serial shards. Each queue attempt invokes `rvw.farm.native_shard`, which
uses the adapter's `run-many --persistent --jobs 1` interface. The adapter must
support that interface. All adapter paths and ELF paths must be absolute.
Start queue workers separately. Each worker inherits the core environment.
Use private core and sbt locks for a private build.

Each retry gets fresh C1 directories under `{attempt_dir}`. The runner checks
ELF hashes and requested options. It refuses process-mode results. It writes
validated C3 `results.json` and `collection.json` beside the C1 cells. Complete
collection can contain DUT failures. Missing, changed or incomplete C1 evidence
keeps collection inconclusive. This runner does not publish C4 gate acceptance.

Queue cancellation and checked recovery allow 25 seconds for cooperative
SIGTERM cleanup before SIGKILL. The native shard wrapper installs a TERM
handler so its adapter group can unwind. Keep cancellation controls separate
from a DUT verdict. A dead controller with a pending cancel does not retry.

`rvw farm live --root QUEUE --owner OWNER --out recorded.html` exports the
same owner-scoped live view as standalone HTML. MCP `farm_live` accepts the
same `out` option. The file embeds recorded trends, per-test history, failure
clusters and referenced C5 summaries. It needs no HTTP service or token.
Review its contents before sharing it. The export contains that owner's
evidence. It does not infer gate acceptance. Cluster bundles written under
`JOB/bundles/CLUSTER_ID/summary.json` appear in live and exported drill-down.

Triage also reads `cosim.json` beside a C1 result. A first-mismatch signature
requires a recorded `rvw.cosim/1` mismatch whose captured ELF and C2 hashes
match that C1 and whose C1 identity matches the C3 entry. Invalid comparisons
produce report issues and retain the original C1 failure signature. Cluster
members retain the comparison hash, model, masks and synchronization records.
`--core-env NAME` adds the source variable to generated `rvw bisect` commands.
These commands bind the recorded good and bad revisions. `execution: not_run`
means that triage has not run bisection.

## Native observation catalogue

`rvw farm observe --db design.db --root RUN --wave-prefix TOP.Module --out
observations.json` reads conclusive C3/C1 evidence and exact waveform signal
names. MCP exposes the same operation as `farm_observe`. VCD, gzipped VCD and
FST are supported. FST conversion uses captured GTKWave tools. The report binds
the database hash, waveform hashes, C1 source/RTL identities, converter inputs
and measured test wall times. It records signals with known-value changes.
Reset and boot activity are included. Missing waves or unmatched names leave
signals unknown, so selection retains those tests. Partial signal observations
are not functional, branch or statement coverage.

Use native `rvw cov merge`, `cov rank` and `cov select` for coverage ranking.
Attach its reviewed selection as `coverage_selection` in the catalogue.
`coverage_selection.tests` are mandatory, even beyond the time budget. Unknown
coverage-test IDs are errors. `fallback_all` still keeps every test. Freeze
the catalogue and plan before executing the candidate. Compare the selected
run with a separate full run. A point-covering subset need not catch a fault.

Budget reports also show recorded C1/C3 DUT outcomes and C4 report counts.
`cost_per_conclusive_dut_observation` divides all scope charges, including
infrastructure attempts, by recorded conclusive C1/C3 observations. Repeated
executions count separately. `cost_per_recorded_gate_report` divides the same
scope charges by unambiguous recorded C4 reports. Missing rates or zero reports
keep unit costs null. Per-C4 groups show only charges of attempts that own that
report. Scope totals can also include upstream simulation jobs. Caller rate
units are not an external provider bill. Budget exhaustion never creates a
verdict or removes a recorded DUT failure.

## Native farm gate intake

`rvw farm gate --base BASE --candidate CAND --project rvw.toml --tier TIER
--rvfi-trace --out verdict.json` checks native C1/C3 identity and invokes the
existing `rvw regress gate` engine. MCP exposes `farm_gate`. Core and harness
must be clean committed revisions. Every cell needs ELF, RTL and captured
native-build hashes. C1/C3 source, outcome, requested options and tools must
agree. Missing or incomplete identities refuse intake. C3 source identity is
marked incomplete when a native shard lacks these fields. Program outcomes
remain recorded. Incomplete identities cannot earn C4 accept.

Native model-build options remain in C3 `native_options`. C3 `options` holds
requested execution options. Config and seed use their existing C3 fields.
The gate's exact plan check remains unchanged. `rvw regress gate --out FILE`
also selects an explicit verdict destination through CLI and MCP.

For queue commands, use `python -m rvw.farm.gate_job` with the same arguments
and `--out {attempt_dir}` as a directory. It writes `verdict.json` and
`rvw.farm-gate/1` collection metadata. Exit zero means a C4 report was collected,
including reject or inconclusive. The public gate CLI retains C4 exit codes.
Queue attempts retain the recorded C4 value and hash. Live history shows that
value separately from execution completion and C3 pass counts. Mixed recorded
verdicts remain mixed. No acceptance is inferred from queue completion.

## Persistent shared plans and offline Kubernetes validation

Add `--persistent --jobs 1 --python /absolute/worker/python` to `farm plan` to
use the persistent C1 server and collect C3 for each shard. All cells must use
one configuration. The worker Python needs `rvw` installed. ELF copies retain
content hashes. Test IDs retain the original manifest names. Local and cluster
executors use the same command and expected result arrays. C3 collection checks
its planned test identities and corresponding C1 outcomes. Collection complete
can contain DUT failures. This check does not publish C4.

```sh
rvw farm batch --plan /shared/campaign/plan.json --action validate \
  --openapi kubernetes-openapi-v2.json
```

MCP `farm_plan` accepts `persistent` and `python`. MCP `farm_batch` accepts
`action: validate` and `openapi`. Validation reads a local official OpenAPI v2
file and checks each rendered `batch/v1` Job. It checks the enclosing `v1` List
separately. It returns the schema and manifest hashes. It makes no API calls.
It does not check admission, quotas, image availability or node execution.

`examples/regression-scale/k8s-example/` contains two rendered Jobs and the
relocated plan from a real local 49-test run. Only paths changed. The 25/24 test
membership, ELF hashes, options and expected C1/C3 cells are the same. The local
run took 54.016 seconds with one simulation at a time. All 49 C1 cells passed.
Both C3 suites were complete. The pinned official schema accepted both Jobs.
A negative control with no `containers` field failed validation.

Use `examples/regression-scale/render_k8s.py` for explicit path relocation and
offline validation. It writes shard manifests but does not copy ELF bytes.
Its example image is an unbuilt placeholder. Do not submit it as a working
image. This native run used macOS tools. It does not establish Linux or cluster
parity. Persistent shared-plan output paths are fixed. Use a new root for every
rerun or retry. The queue-owned submit example instead uses fresh attempt paths.

Triage also reads native C2 trap events for a conclusive failed test whose C1
records traps. It validates the full C2 stream, terminal status, trap count and
C1/C3/header identities. With no first mismatch, the last recorded trap cause
becomes the grouping key. Members retain the original C1 signature, C1/C2
hashes, interrupt flag, value and cycle. A trap before a failure need not be
its root cause. The report states `root_cause: not_established`. Invalid or
unbound trap evidence keeps the original signature and adds an issue. Passing
trap tests do not create failure clusters. A representative C5 retains the
original C1 failure signature even when its cluster uses a trap grouping key.
