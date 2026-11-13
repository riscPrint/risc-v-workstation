# Real Spinal revision examples

These scripts prepare private, committed source copies. They do not edit either
upstream checkout. Use a clean output directory outside this repository.

```sh
source /Users/mahir/fun/saviour/spinal-boom/env.sh
export RVW_HOME="$PWD"
rvw/.venv/bin/python examples/formal/equiv-real/prepare.py \
  --spinal /path/to/SpinalHDL --vex /path/to/VexRiscv --out /path/to/private-cases
rvw/.venv/bin/python examples/formal/equiv-real/run.py \
  --cases /path/to/private-cases/cases.json --out /path/to/proofs
```

The first case copies the real `spinal.lib.math.UnsignedDivider` source from the
selected SpinalHDL commit. It replaces two assignments to the remainder register
with one explicit mux. Both copies use four-bit operands and synchronous reset.
This is an arithmetic control refactor. Pipeline retiming, state recoding and
clock gating remain separate work.

The second case copies VexRiscv's `FpuSqrt` from core revisions `7445c66b` and
`baf7dc82f855eddaf5b0a20a6802c526f127e38a`. The module source is unchanged between
these core revisions. This is a revision-flow control, not evidence for a changed
square-root implementation. Both copies use a four-bit mantissa.

Each case has its own source repository and project file. A separate committed
generator invokes sbt in the archived revision directory. The public
`rvw formal equiv --gold-rev ... --gate-rev ...` command runs the build, selects
the module and invokes eqy. Export logs, source snapshots and RTL remain in the
proof directory. `summary.json` records the command and verdict for each case.

The scripts use `vex-equiv` and `sbt` locks. Builds and proofs use `nice -n 10`.
Each case has a 180-second total budget, including lock acquisition and both
exports. At most one proof runs at a time. A lock timeout is inconclusive.
Twelve startup clocks are unchecked. Inputs then remain free. Invalid response
payloads are still compared. Independent uninitialized datapath registers can
therefore prevent equivalence. No handshake constraint is inferred.

## Limits

These cases check small real components. They do not establish divider arithmetic,
IEEE floating-point behavior, full-width equivalence or whole-core correctness.
The recipe requires cached Scala 2.13.14, sbt 1.10.7 and SpinalHDL 1.15.0 artifacts.
It runs offline. It copies the source, not an existing compiled classpath.

## Recorded run, 2026-11-13

Both cases returned `inconclusive` after 180 seconds. They exhausted the export
budget in the shared `sbt` queue before compilation. Neither case reached eqy.
See `results.json`. The recipe unit test passed. Real native equivalence remains
unproved. Re-run with the same source pins when the build queue is available.
