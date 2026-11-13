# Performance and pipeline events contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Pipeline cause event extension

Kanata 0004 traces can carry version 1 `#rvw` comment records. Fields use literal
tabs. Records use the current cycle cursor. Standard viewers can ignore the
comments. Ordinary stage, dependency and terminal records remain valid.

```text
#rvw<TAB>1<TAB>stall<TAB>scope<TAB>cause<TAB>evidence
#rvw<TAB>1<TAB>replay<TAB>instruction_id<TAB>cause<TAB>evidence
#rvw<TAB>1<TAB>commit<TAB>instruction_id<TAB>kind
```

`scope` and `cause` are nonempty strings without tabs or newlines. Scope names
are project-defined. Common generic causes are `operand_wait`, `structural`,
`load_miss`, `rob_full` and `lsq_full`. `evidence` is `measured` or `inferred`.
A measured cause comes from an explicit sampled reason signal. Inferred adapter
estimates must use `inferred`. Stage residence and dependency `W` edges do not
establish a measured cause.

A stall record covers `[cursor, cursor + 1)`. Emit one sample per blocked cycle.
Several scopes or causes can overlap. Duplicate scope/cause/evidence samples in
one cycle count once. A replay record is one explicit event for a live instruction.
The optional standard `W` record supplies consumer/producer dependency edges.

Commit `kind` is `architectural` or `predicated_off`. Both denote physical commit.
The producer must know the predication flag. The annotation must precede exactly
one R type 0 for that instruction in the same cycle. It must not annotate a flush
or an open instruction at EOF. R type 0 without an annotation has unknown commit
kind. The extension does not change event IPC or C1 counter checks.

`rvw perf/1` adds `stall_causes`, `replays` and `commit_kinds` objects. Counts by
cause can overlap. Measured samples and inferred samples stay separate. Unknown
zero-retirement intervals have no measured sample, including idle cycles. Unit
stalls do not prove that global retirement was blocked. Commit-bubble head states
remain inferred. Readers refuse malformed `#rvw` records, unknown versions and
unknown event kinds. Other comments retain their existing behavior.

### Native job cost reports (first increment, #57)

`rvw.cost/1` records limits, local logical CPU capacity, elapsed wall seconds,
measured child CPU seconds, conservative charged CPU seconds, launched job units,
exit code, status and stop reason. A unit is one launch through `run_group`.
Native descendants within an adapter batch are not separate count units.
A locked command-owned counter covers nested launches. CPU reservation is host
capacity times wall time. Cleanup has a separate grace and remains in the report.
Missing or exhausted budgets cannot grant a gate accept. Reports are external
artifacts. See `rvw/src/rvw/common/README.md` for enforcement limits.

### Native shared result cache (first increment, #53)

`RVW_REMOTE_CACHE=HOST:/absolute/path` adds SSH/rsync transfer to the existing
regression cache. The directory key is the full existing C8 job key. Each new
cache generation contains `.rvw-cache-key` with that exact key. A fetched entry
must have a valid generation inventory, all artifact hashes and an equal stored
key. A missing or partial object is a miss. The existing runner still checks job
parameters and C1 provenance before reuse. Transfer adds no new admission rule.
Uploads send generations before `current`. Downloads use persistent private,
locked staging keyed by remote location and full C8 key. rsync checks checksums
on resume. Only fully verified generations can be published locally. Upload
ownership metadata (`rvw.cache-owner/1`) in `owners/<generation-id>.json` records host, user, key, generation and
upload time. It is not evidence. Explicit native maintenance verifies managed
entries and removes invalid entries, expired entries, then oldest publications
to meet an owner-supplied byte limit. Transfers must be idle during maintenance.
Unmarked directories are not deleted. Evicted or partial entries are misses.

### Native farm collection (first increment, #25)

`rvw.farm/1` records the explicit run-many plan, campaign-local cell IDs, options,
ELF hashes, hosts, per-shard completion, C1 outcomes and missing IDs. `complete`
means collection is complete. It does not mean tests pass or a gate accepts.
`rvw.farm-notifications/1` exports deterministic event IDs, campaign ID, event
kind, subject and details. DUT failures and infrastructure faults are distinct.
Collection-complete events do not claim pass. Delivery is `not_attempted`.
The export is read-only; external consumers own delivery and deduplication.
Host reservation stores are per OS user, not a cross-user admission service.
The static dashboard has no authentication layer.
New reports also carry `campaign_id` and the captured adapter `identity`.
`rvw.farm-classification/1` groups recorded executions by tool identity, ELF
hash and complete options. Every attempt retains its original outcome, source
report path and SHA-256, campaign ID and cell ID. An observed DUT failure keeps
the group failed even after a pass; that combination marks it unstable.
Infrastructure faults and missing outcomes stay separate. Different seeds and
builds cannot establish instability of one fixed execution identity. This is
recorded-outcome classification, not automatic retry or failure waiver.
The controller writes `plan.json` before dispatch and atomically replaces
`progress-N.json` after each validated cell and finished shard. `farm recover`
reads these checkpoints without mutation. Missing `farm.json` always gives an
inconclusive recovered campaign. Missing cells remain explicit. Recovery does
not infer a C1 outcome from unvalidated artifact files or confirm host cleanup.
A shard with a lost connection, wrong identity, missing C1 or invalid artifact
is inconclusive. Results retain their original failure outcomes. C1 config, seed,
ELF hash and every declared identity claim must match. Worker identity documents
must equal the supplied complete `/2` document. SHA-256 binds transferred files.

The first native SSH endpoint buffers transfers and uses a bounded run-many
process group. Separate SSH cancellation uses campaign control tokens. A host
acknowledges only after group cleanup and a host process-table check. Missing
acknowledgement is inconclusive. Host reservations share CPU slots, declared
memory bytes and named locks across workers. They report queue time and release
on handled exit. A persistent FIFO queue prevents newer requests from bypassing
older requests. Dead waiting tickets can be removed; active reservations cannot.
Reservations are cooperative, not OS CPU/RSS limits. Optional host `limits`
apply native hard CPU-seconds, file-byte and open-file limits before exec.
Linux also supports address-space-byte limits. Children inherit limits per
process. Unsupported requested limits fail closed. These are not aggregate
campaign CPU or RSS limits. The shard records its requested limit values. SIGKILL can leave
stale reservations; owner cleanup is required. Scalable streaming, crash recovery
and C3 gate import remain open. The static dashboard reads existing C3/C4/history. Recorded
C3 `ipc` and `coverage` metric samples are plotted by core, suite and config.
Pass rate divides conclusive passes by all recorded C3 tests. Run time sums all
recorded test `wall_s` values only when every value is present and valid. History
charts retain missing runs as gaps. These metrics do not prove plan completeness.
It does not establish bin compatibility or verification closure.
Dashboard filters select exact core, suite, config and gate values, plus a run-ID
substring. Counts and metrics use selected C3 suites. Missing evidence stays
visible when suite/config membership is unknown. Active filters are in the HTML.

## Commit-slot top-down report (`rvw.topdown/1`)

`rvw perf topdown EVENTS [--c2 RVFI] [--result RESULT]` (MCP `perf_topdown`) reads the end
record of an `rvw.probe-events/1` stream. The project binds five counter probes:
`topdown_slots` (commit width each cycle) and `topdown_retiring`, `topdown_bad_speculation`,
`topdown_backend_bound`, `topdown_frontend_bound`. The project owns their per-cycle predicates;
the recommended ones are those of the OoO model's `topdown` partition (`rvw/src/rvw/ooo/README.md`).

```json
{"schema": "rvw.topdown/1", "unit": "commit_slots", "total_slots": 36122, "cycles": 18061, "width": 2.0,
 "slots": {"retiring": 10653, "bad_speculation": 7278, "backend_bound": 17869, "frontend_bound": 322},
 "fractions": {"retiring": 0.295, "...": 0.0}, "status": "checked",
 "checks": {"c2_retirements": 10653, "c1_instret": 10653}, "identity": {}, "source": "...", "method": "..."}
```

The four classes must sum to `total_slots`, or the command fails (exit 2). With `--c2`,
`retiring` must equal the C2 retirement count (records without `trap` and without `event`), and
`status` is `checked`; without it `status` is `unchecked`. With `--result`, `retiring` must also
equal C1 `instret`. A run without an end record fails. The report is a project-bound slot
partition, not hardware top-down counters.
