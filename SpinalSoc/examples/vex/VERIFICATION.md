# SoC verification evidence

Measured on 2026-11-13 with SpinalHDL 1.15.0 and Verilator assertions.
The core revision was `baf7dc82f855eddaf5b0a20a6802c526f127e38a`.
The run used a private core copy and the captured development classpath.
It used the new `verify.S` ELF at seed 31. It passed in 248 cycles.
The working tree contained the implementation changes. This is development
evidence. It is not a committed-revision acceptance result.

```sh
rvw soc verify SpinalSoc/examples/vex/soc.json \
  --manifest SpinalSoc/examples/vex/verify.json --out NEW_DIR
```

Set `VEXRISCV` and `RVW_SOC_CLASSPATH` as described in the example README.
Build `verify.S` with `build-programs.sh`, or use the same GCC command from
that script for only this program. The command runs the native preparation
once, then runs the APB VIP and register oracle on sampled peripheral pins.

| kind | generated | ran | result |
|---|---|---|---|
| protocol | yes | yes | inconclusive |
| registers | yes | yes | inconclusive |
| vip | yes | yes | inconclusive |
| uvm | yes | yes | pass |
| connectivity | no | no | inconclusive |
| decode | yes | yes | proven |
| cdc_rdc | no | no | inconclusive |

The capture contains 158 sampled pin rows and 53 completed transfers.
RAM had 38 transfers. UART had 4. CLINT had 5. PLIC had 4. Finisher had 2.
No peripheral bus was unexercised. The independent register oracle checked
10 reads. It had no unknown-value reads. The program checks UART LCR and
scratch, CLINT MSIP, PLIC priority and enable, and the finisher reset value.
The map does not contain an exercised read-clear or W1C register. Unit tests
check those oracle paths with corrupted-response cases. These unit tests do
not qualify an RTL peripheral's side effects.

The table does not claim complete protocol qualification. Core AXI ingress
pins are not in the capture. The emitted bind files were not compiled in a
separate consumer. Native Spinal fabric assertions were enabled. The real fabric decode target proved seven assertions with `rvw formal
prove` and Yices in three seconds. A decoder mutant changed the UART
selection address from `0x10000000` to `0x10000200`. It failed the same
proof in 1.9 seconds. This proof covers the fabric instance with the map
windows. It excludes core and peripheral state. The separate pyuvm test-master harness passed 17 known-reset reads.
Its passive APB environment independently checked the same 17 reads across
UART, CLINT, PLIC and finisher. Every MMIO bus was exercised. This harness
uses the same device map and simple-bus ingress. It excludes CPU execution.
A wrong UART LCR reset expectation failed the native bench. Formal
connectivity and a multi-domain lint run were NOT RUN. The single-clock program cannot qualify CDC or RDC.

## Native ingress and boundary checks

A fresh composition also binds core AXI channel stability and the existing
SpinalChecks AXI address/read/write transaction rules. The wrapper declares
two read, two write and four combined issuing slots for the checker metadata.
APB checks cover actual peripheral pins after legacy bridges as well as the
fabric-side ports. All five programs (`hello`, `interrupt`, `external`,
`uart_irq`, `verify`) passed with these binds at seed 31. `verify` still
measured 248 cycles and 36 retired instructions. An unsolicited AXI B
response failed `axi4.write_match` in a separate native fixture. A changed
held request address failed the native channel-stability assertion.

These results establish sampled assertion execution. The table's protocol
row remains inconclusive for complete protocol qualification. No AXI stress,
coherence, liveness or multi-domain protocol proof is claimed here.

## Fresh typed consumers

The resumed worker rebuilt the typed extractor against main and ran the Vex
verification command with fresh single-clock and multi-domain databases.
The CPU register program passed at seed 31 in 248 cycles and 36 retired
instructions. The composed pyuvm bench checked 17 known-reset reads.

| kind | generated | ran | result |
|---|---|---|---|
| protocol | yes | yes | inconclusive |
| registers | yes | yes | inconclusive |
| vip | yes | yes | inconclusive |
| uvm | yes | yes | pass |
| connectivity | yes | yes | inconclusive |
| decode | yes | yes | proven |
| cdc_rdc | yes | yes | inconclusive |

The connectivity consumer ran in unbounded mode with a separate activation
obligation. Yosys could not finish the internal binding work within the short
consumer limit. No connectivity proof is claimed. The manifest declares
timer and combined external interrupt transfers, core reset and fabric clock
connections. The latter two are sampled contracts under the formal backend's
reset guard, not clock or reset sequencing qualification.

The multi-domain example places CLINT behind the existing clock bridge at
10 MHz. Its database contains 35 components and 2,334 signals. The existing
CDC/RDC consumer ran on this database. Its detailed report retains structural
findings and unrun metastability, pulse-loss, reconvergence and reset-release
obligations. The table does not claim CDC/RDC signoff. Databases, captured RTL
and command logs remain local development artifacts under `SpinalSoc/out/`.

## Scoped consumer execution

The scoped campaign uses per-connection source cuts, an explicit legal
APB master contract for bounded protocol checks, directed register obligations,
and separate cocotb tests for each MMIO bus. It keeps structural findings
separate from unrun consumers. The native runs use the same private core pin
and seed 31. The private source build passed in 133 seconds.

The source-cut backend first resolves the structural dependency. It then
replaces module bodies outside the observed hierarchy with free output values.
It cuts the actual source driver by canonical Yosys bit ID. Named aliases
remain connected. This avoids RAM initialization and CPU state in a wire proof.
All four declared connections proved with separate activation witnesses.
Transfer proofs took 3.6 to 4.4 seconds. Activation checks took 1.6 to 2.2
seconds.
A native corrupted-transfer test failed, while the unchanged transfer proved.
Clock and reset rows name their actual top-level drivers. They are sampled
value contracts, not sequencing checks.

The protocol campaign runs all 49 selected ISA programs in one composed
Verilator build with assertions. The bounded target checks 31 fabric assertions
at depth 8. Its legal-master assumptions are emitted with `includeFormal`.
This covers bounded APB fabric safety and sampled CPU AXI assertions. It does
not establish complete AXI ordering, coherence or liveness.

The directed register program checks ten known-value reads. Its explicit
write/read obligations cover UART scratch, CLINT MSIP and PLIC priority 1.
The selected map has no read-clear or W1C register under these obligations.
Those semantics remain outside this RTL campaign.

Each generated peripheral VIP test resets the composed RTL and uses its own
APB monitor and register oracle. UART checks three reads. CLINT checks three.
PLIC checks ten. Finisher checks one. These are four separate cocotb tests on
an independent-master composition. They do not execute the CPU.

The multi-domain structural report retains two clock sources, 293 registers,
nine CDC paths and 2,507 findings. It recognizes `BufferCC` and
`FlowCCUnsafeByToggle`. Two paths are synchronizer candidates. Another 1,561
reset paths have no structural hazard. These are different classifications.
The seven unrun temporal rule groups remain in the detailed report.
Structural findings require review. They do not establish a silicon failure
or a CDC/RDC acceptance result.

The fresh combined run produced this table:

| kind | generated | ran | result |
|---|---|---|---|
| protocol | yes | yes | pass |
| registers | yes | yes | pass |
| vip | yes | yes | pass |
| uvm | yes | yes | pass |
| connectivity | yes | yes | proven |
| decode | yes | yes | proven |
| cdc_rdc | yes | yes | findings |

Each pass has the scope stated above. The structural findings require review.
