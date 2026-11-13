# Finite coherence model

Run from the repository root:

```sh
python3 SpinalChecks/coherence/model.py
python3 -m unittest discover -s SpinalChecks/coherence -v
python3 SpinalChecks/coherence/model.py --bug stale_data
python3 SpinalChecks/coherence/model.py --generate SpinalChecks/src/main/scala/spinalchecks/coherence/PermissionRelation.scala
```

The checker uses breadth-first exploration and a nonterminal cycle check.
It uses only the Python standard library. No external solver is needed.
Exit codes are 0 for pass, 1 for a counterexample and 3 for an exhausted budget.
A JSON report states the model scope. The report is a local tool interface.
A pass applies only to the finite model. It is not a C1 run or C4 gate verdict.

## Model

Two agents share one home and one line. Each issues one AcquireBlock request,
for Branch or Trunk permission. A home transaction has probe, acknowledgment,
grant and completion phases. The home selects either queued request.
A Trunk recipient performs one local write at its GrantAck step. This merges
an abstract local write with E completion. It does not give E a data payload.
Completed agents can release a copy. T releases return the current data.
Every Trunk copy is conservatively treated as dirty.
The data alphabet is {0, 1}. A write toggles the value.
See [the design](../../docs/design/coherence-mc.md) for omitted TL-C features.

The invariants check exclusive ownership, valid-copy data and home data when
no Trunk copy exists. Finite request completion is the progress target.
A nonterminal state without a successor is deadlocked. A nonterminal cycle
fails the stronger cycle-exclusion progress condition. Environment stutter is
omitted. Eventual enabled steps are assumed. No general fairness proof is made.

Seed defects: `grant_conflict`, `stale_data`, `lost_ack`, and `retry`.
Each must fail with a replayable witness. Do not generate monitors from a
mutated or incomplete graph.

## Generated permission monitor

`PermissionRelation.scala` contains the graph's permission projection and its
finite-path closure. `PermissionMonitor` builds RTL expressions from that table.
Both inputs must belong to the monitor clock domain. Reset initializes the
previous pair to N/N. Values are N=0, B=1 and T=2. Unused encoding 3 fails.
Expose `failed` to simulation. The monitor also emits a Spinal assertion.
The generated relation can be used directly by software simulation monitors.

The projection hides data, home phases and request history. The finite-path
closure permits a shrink and grant in one clock. This weakens it to permission
safety; it does not check channel sequencing, dirty data or progress on RTL.
`CoherenceModelFixtureSpec` runs both forms on the two-hart `AtomicFixture`.
That fixture has no TileLink-C channels. Its fault 4 grants conflicting ownership.

```sh
cd RiscvSim
../scripts/with-lock.sh sbt nice -n 10 sbt 'testOnly riscvsim.CoherenceModelFixtureSpec'
```

## Decisions and limits

Extend SpinalChecks instead of adding a separate platform tool. Reuse its
Spinal assertions and the existing fixture. Keep the generator deterministic.
The initial checker is Python because this graph is small and needs no solver.
A second independent TLC or Murphi encoding remains necessary before broader
protocol claims. MESI/MOESI profiles and real TL-C RTL bindings are follow-up work.

## Named weak-fairness progress

`python3 SpinalChecks/coherence/model.py --fair` exhausts the finite request
model and checks each hart's completion target in turn. `fair.py` finds
strongly connected components in the subgraph where that target remains
incomplete. Each pending state has an environment stutter edge. Named
assumptions cover per-hart issue, arbitration, probe, response and acknowledgment
steps. An action set that stays enabled throughout a component must have an
edge within it. A tour can then satisfy every named weak-fairness condition.
A fair component without completion is a counterexample. A missing response
can therefore fail even when unrelated harts keep completing work.

The report lists assumptions, bounds, a prefix to the failing component and
its internal action labels. State-budget exhaustion is inconclusive. Retry
cycles and lost acknowledgments fail. The unmutated finite graph passes under
its declared fairness assumptions. This is weak fairness on the finite model.
It does not establish unbounded RTL liveness. Channel queues, multiple active
transactions, MESI/MOESI directory profiles, TLC/Murphi cross-checks and actual
TileLink-C refinement remain open.

## Queued MESI and MOESI profiles

`python3 SpinalChecks/coherence/directory.py --profile moesi --requests 2`
runs the queued directory abstraction. `rvw memory directory` and the memory
MCP tool expose the same experiment. Each A/B/C/D/E queue holds one whole
message. The home has one active transaction per line. Two lines can have
active transactions at the same time. Each client has one program request
outstanding. Repeated requests can hit a valid copy or request an upgrade.
Writes from Shared/Owned copies retain the local data while the home invalidates
peer copies. These are abstract upgrades, not a full AcquirePerm channel encoding.

MESI reads can receive Exclusive permission. MOESI intervention can retain a
dirty Owned copy while another client receives Shared data. Memory can remain
stale only while an owner or a transfer buffer holds the latest data. Separate
invariants check exclusivity, valid-copy bytes, intervention data and home data.
Writes toggle a two-value alphabet. Each client can choose reads or writes to
one or two lines for up to three requests. Queue occupancy gives backpressure.
No request deadline is renewed by an unrelated response.

The model reuses named weak-fairness SCC checks. Defects cover lost responses,
stale data, early grants, starvation and a cyclic C/D wait. The report retains
bounds, assumptions and incomplete-search status. Native Python exhausted the
MOESI two-request/one-line graph at 627 states and the one-request/two-line
graph at 391 states. Those counts apply to these exact bounds.

Limits: whole single-beat messages, no voluntary eviction, no source/sink ID
allocation, no speculative rollback and no reset during a transaction. The
TileLink channel monitor is a separate implementation. No refinement relation
or TLC/Murphi cross-check is established by these model tests.
