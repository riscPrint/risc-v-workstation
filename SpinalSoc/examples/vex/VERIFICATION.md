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
