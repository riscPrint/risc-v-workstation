# Farm and job queue contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Farm impact selection

`rvw.impact-selection/1` binds test observations to a design database hash.
It retains mandatory tests and unknown effects, reports deadline overruns and
uncovered signal paths, and ranks optional tests by marginal impact per second.
Existing coverage-selection fallback is preserved. Selection is advisory and
cannot earn gate acceptance. Recorded wall times are estimates, not guarantees.

## Farm failure clusters

`rvw.failure-clusters/1` retains original per-test evidence and source identities.
Clusters preserve core/configuration and infrastructure/DUT category boundaries.
Known-failure matches do not waive failures. C5 creation uses one representative
per cluster with reruns disabled. The optional diff uses existing C3/C4 identity
and seed checks; missing or changed evidence cannot establish a fix.

## Queue cumulative budgets

`rvw.queue-cost/1` records cumulative run, agent or project usage and configured
limits. Core-hours equal declared cores times attempt wall seconds divided by
3600. Attempts include retries, cancellation and cleanup. Active attempts reserve
their bounded maximum charge during admission. A worker timeout enforces the
smallest remaining scope limit; cleanup can exceed that limit and stays charged.
Execution states do not replace C4 verdicts. Monetary cost requires an explicit
rate; absent rates stay null.

## Persistent farm service queue

`farm queue` stores jobs and an ordered event log in SQLite under its selected
root. Each job retains an owner, priority, command, retry bound, timeout and all
attempt outcomes. `complete` means process completion with exit zero, not a C4
accept or a DUT pass. Worker death is an infrastructure error. Unchecked process
groups require cleanup and cannot earn cancellation acknowledgement. The HTTP
service maps bearer tokens to owners and restricts job reads and cancellation.

## Batch shard execution

`farm batch` accepts one explicit command and expected C1/C3 result paths per
shard. The same commands run locally or as batch/v1 Jobs. Project-supplied PVCs
hold inputs, caches and results. Collection validates schemas and declared C1
identity claims. Missing cells are explicit and inconclusive. Job process success
and collection completeness do not establish C4 acceptance. Kubernetes retries
are disabled; retry policy belongs to the controller.

## Persistent agent workflow plans

Farm workflow plans retain node IDs, command arrays and dependency IDs separately
from verification evidence. Queue jobs bind workflow/node IDs for resume. Only
completed dependencies admit a node. The SQLite event sequence supports SSE
replay by Last-Event-ID. HTTP event access is restricted to the token owner.
Workflow completion means execution complete, not a C4 acceptance or DUT pass.

## Live farm views and checked crash cleanup

The owner-scoped live view reads validated C3 observations from owned job
folders. C5 reads stay within that job. Trends retain absent samples. Queue
attempt directories separate retry evidence. Explicit C1 DUT retries retain
all failures; identity-matched mixed outcomes can mark instability but cannot
waive a failure. SSH crash cleanup requires checked process start identities
and no live owned groups before releasing the dead worker's reservations.

## Shared C1 batch shard plans

`farm plan` copies ELF inputs by hash and writes one run-many manifest per shard.
Every expected cell binds its ELF hash, config, seed and declared options.
Additional identity claims cannot override manifest identities. Local and cluster
executors consume the same command/result plan. Shared PVC paths must match the
collector path. Collection never promotes process success to a DUT/gate verdict.


## C4 cost attribution

Queue cost reports attribute each attempt once to schema-checked recorded C4
reports within its attempt directory. Links retain original paths and SHA-256.
Missing C4 is not_recorded; invalid or multiple reports are ambiguous. Execution
state stays separate from the recorded verdict. No acceptance is inferred.
Active budget reservations can keep work queued; permanently exhausted scopes
cannot block another owner's admissible work.

## Cluster collection state

Cluster collection requires the exact planned Job IDs and current successful
Complete conditions. Missing IDs, failed/incomplete Jobs or query errors make
collection inconclusive, even when artifacts exist. Valid returned evidence is
retained. Empty expected-cell plans are refused. Collection does not infer a
DUT pass or C4 acceptance. Long farm MCP calls use owned worker processes.

Failure clusters can include commit ranges when both sides record full commit
IDs. Short or unknown IDs do not create ranges. Range links do not replace the
C3 input/seed identity checks used by regression comparisons.

## Native persistent shard collection

The local shard runner writes `rvw.native-shard/1` to `collection.json`.
It records expected and collected cells, errors, adapter return code, wall
seconds and tests per second. Wall time includes adapter startup and collection.
Only validated persistent-server C1 cells enter the adjacent C3 file. Missing
cells keep collection inconclusive. Each queue retry uses its own attempt
directory. Collection completeness is not a DUT pass or a C4 verdict.

Queue cancellation sends SIGTERM first. It allows 25 seconds for a wrapper to
stop nested native groups before SIGKILL. Checked recovery uses the same grace
period. A recovered cancellation stays cancelled and must not launch a retry.

## Recorded live dashboard export

The optional `farm live --out` embeds one owner-scoped snapshot and its C5
summary documents in standalone HTML. The export uses the live view renderer.
It does not embed authentication tokens. Script payloads escape less-than
characters. Unknown or absent bundle documents remain errors. Cluster bundles
can use `JOB/bundles/CLUSTER_ID/summary.json` or the existing per-cell location.

Native shard exit code 1 is collection complete only when every expected C1
cell is valid and conclusive and at least one cell failed. Exit code 1 with
only passes remains inconclusive. Farm history discovery treats a C5 summary
and its owned storage as a bundle, not as a C3 regression generation.

## Comparison-backed failure signatures

Triage can read a C1 cell's `cosim.json` (`rvw.cosim/1`). It checks C1/C3 core,
configuration, seed, status and ELF identity. It requires captured ELF and C2
hashes before it uses first-mismatch PC and instruction values. Missing or
invalid comparison evidence does not waive the C1 failure. Invalid evidence
adds an `issues` entry. Members retain comparison hashes and reference-policy
metadata. Generated bisect command arrays retain their revision range and
`execution: not_run`. Generating a command is not bisection evidence.

## Native impact observations

`rvw.impact-observations/1` is a farm selection catalogue. It records exact
waveform/database name matches, known-value changes, measured wall seconds,
database and waveform hashes, C1 source/RTL identities and waveform capture
metadata. Unknown observations omit `signals`. The selector keeps them
mandatory. Signal activity includes reset and boot. It is partial evidence,
not functional coverage or gate acceptance. Coverage selection `tests` remain
mandatory regardless of the time budget. Unknown required test IDs are errors.

## Recorded outcome unit costs

`rvw.queue-cost/1` adds recorded C1/C3 outcome counts and C4 report counts.
The two scope unit-cost fields divide all charged scope attempts by conclusive
DUT observations or by unambiguous recorded C4 reports. Repeated executions
count separately. Per-C4 group costs cover only attempts owning those reports.
Missing rates and zero denominators produce null. These fields do not infer
DUT pass, C4 acceptance, measured CPU use or an external provider bill.

## Native C4 gate intake

Native intake binds each C3 cell to C1 source, outcome, requested options,
ELF, RTL and complete native-build identities. Core and harness revisions must
be clean commits. Dirty or missing native identities mark shard C3 source
identity incomplete. Recorded DUT outcomes remain unchanged. C3 `options`
contains requested execution options; `native_options` retains C1 model options.

`rvw.farm-gate/1` is queue collection state. A complete report names its
recorded C4 verdict. It does not imply accept. Queue attempts retain C4 verdict
values and report hashes. Live history keeps those values separate from C3
outcomes. The underlying C4 comparison and requested-plan checks are unchanged.

## Persistent shared-plan collection and offline validation

`farm_plan` accepts `persistent` and worker `python`. Persistent mode requires
one configuration and one adapter server per shard. Expected C1 paths use
`shards/N/cells/M/result.json`. Each shard also expects C3 `results.json` and
an ordered list of test IDs, seeds, ELF hashes and relative C1 paths. Collection
checks these claims and C1/C3 core, configuration, source and status agreement.
An incomplete-source marker records missing identity without changing source
comparison. These checks establish collection only. They do not earn C4 accept.

`farm_batch` action `validate` requires a local OpenAPI v2 `openapi` path.
`rvw.k8s-offline-validation/1` records `valid` or `invalid`, Job count, errors,
OpenAPI SHA-256 and canonical rendered manifest SHA-256. Cluster execution and
admission remain `not_run`. The enclosing document must be a nonempty `v1`
List. Each item must be a `batch/v1` Job and satisfy its schema definition.
This is structural validation. It is not Kubernetes admission or runtime proof.
