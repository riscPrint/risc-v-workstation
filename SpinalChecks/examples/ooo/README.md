# Tiny out-of-order fixture

This is a tool fixture, not a RISC-V core. It has two architectural names,
eight physical tags, four ROB slots, a ready/select issue queue, and four
store slots. A younger ready instruction can issue first. Commit stays in
ROB order. Mispredict discards speculative entries and restores the committed
map. A load selects the youngest eligible older store.

Run from this directory with JDK 21, sbt and Verilator:
`../../../scripts/with-lock.sh sbt-csr nice -n 10 sbt -batch 'runMain spinalchecks.examples.ooo.Run'`.
The fixed seed is 17. Each design runs 1200 random cycles.
The runner requires zero clean firings and the matching check for each bug.
`bindings.properties` names the fixture signals used by the bindings.
Unknown names stop elaboration.

| Variant | Changed behavior | Expected check |
|---|---|---|
| clean | none | no firing |
| leak | commit does not return the old tag | freelist.conservation |
| double_allocate | allocate a mapped physical tag again | freelist.allocate |
| commit_order | retire the next ROB slot before the head | queue.order |
| not_ready | select an operand that is not ready | execution.operands |
| young_store | select a store younger than the load age | store.forward_age |
| stale_map | recovery leaves an uncommitted map value | recovery.map |
| lost_flush | recovery retains ROB occupancy | recovery.flush |

Set `RVW_OOO_FORMAL=1` to emit formal RTL and inventories under `out/VARIANT`.
Use the connected-check preparer at depth 16. Select the expected check ID for
each negative variant. A bounded clean result is not an unbounded proof.
The 16-bit serial age can wrap. The short fixture runs do not qualify wraparound.

The fixture binds FIFO capacity, occupancy and order and arbiter checks from
the library. Its free-list, operand, forwarding and map checks are explicit
project declarations. It does not bind every microarchitecture template.
The complete RecoveryChecks generation-tag and fence interface is not bound.
The forwarding reference checks selection, not byte masks or a cache.

Probes record rename, ROB and IQ occupancy and flush events. They are enabled
only by the runner. The ROB head is also a fault site.
A consumer can sample these with RiscvSim's ProbeCollector.
`rvw perf` needs a Konata stage/retire stream; occupancy probes alone do not
supply one. Add accepted rename, issue and retirement stage events before
using this fixture for that consumer.
The OoO timing model needs an instruction trace and a project timing model.
This fixture has no ISA decoder or C2 trace, so direct timing correlation is
not supported. `rvw fault` can select the probed ROB-head register after a
design-database extraction; a simulation adapter must apply each fault.

## Recorded native results

`native-results.json` records all eight 1200-cycle runs. Clean has zero
firings. Each negative variant fires its expected rule.
`formal-results.json` records all seven matching depth-16 failures and ten
clean depth-16 passes. Clean free-list conservation timed out at depth 16
with both 30-second and 60-second limits. It passed at depth 8 with its
trigger reached. The depth-16 campaign remains inconclusive.
Run `../../../rvw/.venv/bin/python run-formal.py` after formal RTL generation.

## Expanded bindings and consumer runs

The [follow-up record](followup-results.json) supersedes the original native
counts above. The fixture now has 68 inserted checks. Five asserted rename
helpers check occupancy, map/free disjointness, free capacity, unique ownership
and previous-tag chains in ROB age order. ExecutionChecks and RecoveryChecks
bind each slot. Per-slot references cover broadcast wake and multi-slot kill.
The added fence input stops dispatch until the ROB drains. The native runner
exercises fences. Replay and device effects have no implementation in this
fixture. Their reference inputs stay inactive. Their activation is not claimed.

`prove-conservation.py --out DIR` prepares conservation with all five helpers
asserted. No helper is assumed. Use `--mode bmc --depth 16 --engine 'abc bmc3'`
for a bounded job. Short induction and PDR attempts remain inconclusive unless
the result explicitly passes. A passing short base case is not induction closure.

Stage, retire and per-entry flush probes now feed ProbeCollector. The runner
writes `probe-events.jsonl`, `rvfi.jsonl` and C1 `result.json` beside each variant.
The C2 file is a command projection. Each retired destination/data command is
encoded as `addi x(destination+1), x0, data`. It does not represent a RISC-V
instruction decoder, executed ELF or memory-access trace.

Run these consumer smoke checks from the workstation root:

```sh
rvw probes convert SpinalChecks/examples/ooo/out/clean/probe-events.jsonl --to kanata --out /tmp/ooo.kanata
rvw perf /tmp/ooo.kanata --json
rvw ooo SpinalChecks/examples/ooo/timing.json SpinalChecks/examples/ooo/out/clean/rvfi.jsonl --json
rvw probes convert SpinalChecks/examples/ooo/out/clean/probe-events.jsonl --to fault-sites --out /tmp/ooo-sites.json
rvw fault plan --sites /tmp/ooo-sites.json --kinds flip --window 100:101 --samples 1 --seed 17 --out /tmp/ooo-plan.json
rvw fault run --plan /tmp/ooo-plan.json --adapter 'rvw/.venv/bin/python SpinalChecks/examples/ooo/adapter.py' --elf SpinalChecks/examples/ooo/bindings.properties --out /tmp/ooo-faults --jobs 1 --timeout 120 --json
```

The fault adapter runs this fixed-seed command fixture. The `--elf` input is a
fixture identity file for the campaign contract. It is not decoded or executed.
The adapter accepts a flip of either bit in `head`. It confirms read-back before
it reports injection. The recorded campaign has one injected and detected fault.
This sample does not qualify a detection rate.

The recorded probe conversion has 257 retirements, 144 flushed commands and
three open commands. Perf consumes the converted stream. The fixed-latency
OoO model consumes 257 projected commands in 260 model cycles. Its accuracy
status stays inconclusive. This is a consumer smoke result, not RTL timing
correlation. The fixture's random wake and flush inputs differ from that model.

The current six-assertion conservation group passes ABC BMC3 at depth 16 in
16 seconds. Its activation cover passes at depth 16. Depth 12 also passes.
SMTBMC induction and ABC PDR time out under the short limits. Unbounded
conservation remains inconclusive. The earlier depth-16 timeout is historical.
