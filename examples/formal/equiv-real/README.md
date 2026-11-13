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

## Real multiplier hardware configurations

`prepare-mul-configs.py` copies the committed `MulSpliter` and
`AdderAggregator` helpers from VexiiRiscv `Utils.scala`. It creates two private
source revisions. The first uses 17-bit partial products. The second uses 9-bit
partial products. Both retain the default arithmetic sum settings, `(44,8)`
and `(1000,1000)`. Only the split size changes between the revisions.

```sh
rvw/.venv/bin/python examples/formal/equiv-real/prepare-mul-configs.py \
  --source /path/to/private/VexiiRiscv --out /path/to/mul-cases
rvw/.venv/bin/python examples/formal/equiv-real/run.py \
  --cases /path/to/mul-cases/cases.json --out /path/to/mul-proofs --timeout 240
```

Both eight-bit inputs are signed and extended to 33 bits inside the wrapper.
EQY compares the full 64-bit product. It does not assume internal matches.
The helpers are combinational. The clock and reset ports serve the revision
flow's interface. This check covers neither full-width input space nor the
core's multiplier pipeline and control.

The pinned native run proved the output equivalent in 230.351 seconds,
including both exports. The source revision was `9f70315d`. The full revision,
source hashes, RTL hashes, private comparison revisions and proof restrictions
are in `mul-config-results.json`. The public recipe produces the same Scala
component and exporter bytes as the native run. Its provenance records the
hash of the exact upstream source bytes, including trailing whitespace.

## Real FIFO memory refinement and internal observations

`prepare-fifo.py` instantiates SpinalHDL 1.15.0 `StreamFifo` with four eight-bit
entries and asynchronous reads. The comparison revision changes `useVec` from
false to true. Both configurations use synchronous reset. The actual library
implementation supplies the RAM and register-vector storage paths.

```sh
rvw/.venv/bin/python examples/formal/equiv-real/prepare-fifo.py \
  --out /path/to/fifo-cases
rvw/.venv/bin/python examples/formal/equiv-real/run.py \
  --cases /path/to/fifo-cases/cases.json --out /path/to/fifo-proofs \
  --memory-map --timeout 240
```

The wrapper compares push readiness, pop validity, occupancy, availability and
valid pop payloads. It drives the observed payload to zero when pop is invalid.
This is an explicit stream observation rule. Inputs remain free. Flush,
simultaneous push/pop and backpressure are not constrained. Initial storage is
independent. No RAM word equality or internal state equality is assumed.

The native revision run proved all five outputs in 32.047 seconds, including
both exports. Exact finite-memory lowering used `memory_map -formal`.
The captured source has 32 payload storage bits per configuration. The recorded
mapping state counts also contain temporary and control registers. They do not
measure RAM capacity. This check does not cover an abstract array, larger RAM,
a banked memory, synchronous-read latency changes or an external memory model.

`equiv-partitions --memory-map` also proved all four automatically matched FIFO
control observations in 53.271 seconds. The output proof ran first. Each
internal observation then had its own closed proof. No cut equality was assumed.
Unmatched payload storage remains explicit in the receipt. The flow does not
claim complete internal register correspondence.

The recoded four-bit divider also passed its output proof and five matched
register observations in 33.348 seconds. The original control bit and new
one-hot `stateCode` remain unmatched. Five proved observations are not a proof
of a relation for every register.

See `memory-partition-results.json` for source, artifact and native result
identities. Use the captured `gold-export/module.v` and `gate-export/module.v`
files to reproduce the closed internal proof:

```sh
scripts/with-lock.sh vex-equiv nice -n 10 rvw formal equiv-partitions \
  --gold /path/to/fifo-proofs/fifo/gold-export/module.v \
  --gate /path/to/fifo-proofs/fifo/gate-export/module.v \
  --top MemoryFifo --reset reset --memory-map --max-partitions 64 \
  --timeout 180 --out /path/to/fifo-internal-proofs
```

A negative control flips bit zero of each valid payload in the vector revision.
The same revision flow returned `not_equivalent` in 47.645 seconds. The other
four interface partitions still passed. This counterexample is an intentional
wrapper defect. It is not a fault in the library FIFO.
