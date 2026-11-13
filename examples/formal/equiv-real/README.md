# Real Spinal revision examples

These scripts prepare private, committed source copies. They do not edit either
upstream checkout. Use a clean output directory outside this repository.

```sh
source /path/to/workstation/env.sh
export RVW_HOME="$PWD"
rvw/.venv/bin/python examples/formal/equiv-real/prepare.py \
  --spinal /path/to/SpinalHDL --vex /path/to/VexRiscv --out /path/to/private-cases
rvw/.venv/bin/python examples/formal/equiv-real/run.py \
  --cases /path/to/private-cases/cases.json --out /path/to/proofs --timeout 240
```

The first case copies the real `spinal.lib.math.UnsignedDivider` source from the
selected SpinalHDL commit. It replaces the two control registers with a
three-state one-hot register. Both copies use four-bit operands and synchronous
reset. The decoded next-state logic keeps the original assignment priority.

The second case copies VexRiscv's `FpuSqrt` from core revision `7445c66b`.
It compares single-file and one-file-per-component export configurations.
Both use the same module source and a four-bit mantissa. This checks equivalent
export settings. It does not check two different arithmetic implementations.

Each case has its own source repository and project file. A separate committed
generator invokes sbt in the archived revision directory. The public
`rvw formal equiv --gold-rev ... --gate-rev ...` command runs the build, selects
the module and invokes eqy. Export logs, source snapshots and RTL remain in the
proof directory. `summary.json` records the command and verdict for each case.

The scripts use `vex-equiv` and `sbt-equiv` locks. Builds and proofs use `nice -n 10`.
Each case has a 240-second total budget, including lock acquisition and both
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

The initial shared-lock attempts returned `inconclusive` before compilation.
The private-lock retry proved the recoded four-bit divider equivalent.
It took 138.503 seconds, including both source exports. All five output
partitions passed. Reset is synchronous. Twelve startup clocks are unchecked.
This result covers free inputs after startup, including flush and backpressure.

The first square-root configuration attempt reached export but used its
240-second budget after a lock wait. It remains inconclusive.
The ledger retains each attempt. No timeout counts as a proof.

The isolated square-root retry also exhausted 240 seconds. EQY proved the
input-ready partition. It did not finish the raw result payload partitions.
The aggregate verdict remains inconclusive. Raw invalid payloads are compared.
No valid-payload constraint, initialization assumption or core change was added.
See `private-lock-results.json` for the new attempts and native proof reports.

## Smaller real-module configuration check

Use `prepare.py --sqrt-width 2` to select a two-bit mantissa.
Widths below two are refused because the upstream module reads two operand bits
per iteration. The default remains four.

The native two-bit case proved equivalent in 93.135 seconds, including both
source exports. All four interface partitions passed. It compares single-file
and one-file-per-component export settings for the same committed VexRiscv
`FpuSqrt` source. Reset and twelve unchecked startup clocks are the same as
above. Inputs remain free after startup. Raw payloads are compared.

This is a complete result for this small module and these export settings.
It does not prove square-root arithmetic, IEEE behavior, a hardware parameter
change, or the larger mantissa case. The four-bit timeouts remain in the ledger.
See `two-bit-results.json`.
