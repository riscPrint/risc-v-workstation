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

