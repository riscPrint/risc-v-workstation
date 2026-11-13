# Retirement event boundaries

The typed `retired` counter and C1 `instret` use different upstream events.
The count difference is not a fixed two-cycle sampling loss.

`ProbeTapPlugin` counts `WhiteboxerPlugin.commits.ports.valid`. Upstream
`WhiteboxerPlugin` builds these ports from execute-lane `trapAt` controls.
A port fires when `ctrl.down.isFiring && ctrl.down(COMMIT)` is true.

C2 uses upstream `VexiiRiscvProbe`, through `C2Backend.commit`. In
`checkPipelines`, a completion sets `microOp.retireAt = cycle + 1` and its
`commit` flag. `MicroOpCtx.done` tests whether `retireAt` was set. It does not
wait for that cycle. `checkCommits` then drains completed micro-ops in order
and calls the backend. A completed instruction can therefore enter C2 before
it reaches the whitebox commit port at `trapAt`.

`C2Backend.commit` increments its count. A completed `tohost` store sets the
adapter's finish flag. The upstream drain loop can still emit other completed
instructions in the same callback. `VexiiAdapter` finishes the run after that
callback. It does not wait for all those instructions to reach `trapAt`.
The last C2 records can share the end cycle while the commit-port stream ends
earlier.

## Native evidence

The source pin is `9b63f47fe559dbba7874af9196746412fa1294c1`.
`counter-boundaries.json` records the source, input hashes, counts and unmatched
C2 tail. It includes the original cacheless case with seed 1 and seeded memory
latency. The cached cases use seed 7 and memory latency 0.

| Config and program | C1/C2 count | Typed commit count | Difference |
|---|---:|---:|---:|
| `rv32im`, `branches` | 35660 | 35658 | 2 |
| `rv32im_cached`, `smoke` | 18 | 17 | 1 |
| `rv32im_cached`, `branches` | 35661 | 35659 | 2 |
| `rv32im_cached`, cache sweep | 3344 | 3342 | 2 |

Every observed commit-port PC sequence equals the C2 prefix. The remaining C2
records are at the tail. These runs ended in a conclusive pass. The cached
ISA campaign also matched all 49 selected programs against Spike.

The typed counter retains its commit-port meaning. The C1 counter retains the
upstream completion-based meaning. No constant is added to either count.
Performance reports retain the mismatch. A tool that needs equal counters must
select one event boundary at the producer. It must also set an end condition
at that boundary. It must not normalize a saved count.

## Sources

The upstream source files are `test/WhiteboxerPlugin.scala` and
`test/VexiiRiscvProbe.scala` under `src/main/scala/vexiiriscv/` at the pin above.
The adapter sources are [ProbeTapPlugin](../src/main/scala/rvwvexii/ProbeTapPlugin.scala),
[C2Backend](../src/main/scala/rvwvexii/C2Backend.scala), and
[VexiiAdapter](../src/main/scala/rvwvexii/VexiiAdapter.scala).
