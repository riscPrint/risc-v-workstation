# Cocotb examples

This folder tests one small Spinal-generated counter and the unmodified upstream
VexRiscv `vexriscv.plugin.PmpSetter(2)` unit. Bindings and test oracles stay here.
The PMP test checks aligned NAPOT base and mask formulas for 29 region sizes
and eight seeded addresses per size. It does not test the complete PMP plugin
or privilege enforcement. The counter checks reset, increment, wrap and hold.

Set `RVW_HOME` to the workstation checkout. Set `VEXRISCV` to the upstream core
checkout. Use JDK 21 and the dependencies in the parent README. From this folder:

```sh
cd ../rvw
"$RVW_HOME/scripts/with-lock.sh" vex "$RVW_HOME/scripts/with-lock.sh" sbt \
  nice -n 10 sbt -J-Xmx2g -batch -Dsbt.offline=true \
  'runMain rvwvex.CocotbUnits ../cocotb/rtl'
cd ../cocotb
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  counter-icarus.json --out out/counter-icarus --seed 1 --json
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  counter-verilator.json --out out/counter-verilator --seed 1 --json
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  pmp-icarus.json --out out/pmp-icarus --seed 1 --json
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  pmp-verilator.json --out out/pmp-verilator --seed 1 --json
```

Install `rvw[cocotb]` first. Each output directory must be new. RTL and outputs
are ignored by Git. See [adapter contracts and limits](../../../rvw/src/rvw/sim/README.md).

## PLIC controller adapter

`rvwvex.PlicUnit` emits the unmodified SpinalHDL 1.15.0 PLIC library with
three level sources, two target contexts and an APB3 register interface.
`plic_bus.py` drives that interface. Expected state comes from the independent
Python PLIC reference. The test changes source levels during APB accesses.
It checks arbitration, tie breaking, threshold, shared pending state and
claim/complete gateway behavior across both contexts.

Generate RTL with the same setup as above. Replace the main class with
`runMain rvwvex.PlicUnit ../cocotb/rtl`. Then run:

```sh
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  plic-icarus.json --out out/plic-icarus --seed 1 --json
```

`claim_must_ignore_threshold` is a conformance test for a known source-level gap.
The library gates the claim value with the interrupt threshold. The reference
requires a claim to select an enabled pending source regardless of threshold.
A mismatch makes the native suite fail. Do not waive this failure.
The ratified [PLIC 1.0.0](https://github.com/riscv/riscv-plic-spec/blob/master/riscv-plic.adoc#interrupt-claim-process)
separates notification masking in Priority Thresholds from claim selection.
It explicitly states that threshold does not affect claim. It also permits
polling claims with threshold set to maximum. Interrupt Completion rearms the
gateway; it does not weaken the claim rule. Thus an enabled pending source at
priority 3 must be claimed with threshold 3, even while notification is low.
Both the library RTL and installed Spike return zero in this case. Their
agreement does not override the specification.
The other test checks the directed arbitration sequence. A CPU is not connected to this component
adapter. Real-core PLIC delivery and full simultaneous context arbitration
remain open in #131. Do not use this suite to claim complete PLIC compliance.

## Core reset lifecycle

`rvwvex.LifecycleUnit` uses the unchanged VexTop configuration. It adds output
observations for privilege, machine status and WFI activity. Generate it with
`runMain rvwvex.LifecycleUnit ../cocotb/rtl` under the same `vex` and `sbt` locks.
Run `reset-icarus.json` with `rvw regress cocotb` under the `vex` lock.

The test pulses synchronous reset on one native instance. It checks cold reset
and three rounds of warm reset during a stalled fetch, a stalled data request
and ECALL trap entry. The declared contract checks M-mode, MIE/MPIE clear,
MPP=M, invalid retirement and trap outputs, and the first fetch at 0x80000000.
Each reset discards harness-owned bus responses. General-purpose registers
have no reset contract here. The test does not use their initial values.
The current example has no local reset or debug port. Those parts of #111
remain open. A system reset does not establish local reset behavior.

## WFI and stopped clock

Generate `LifecycleUnit` as described above. Install RISC-V GCC on PATH.
Run `wfi-icarus.json` with `rvw regress cocotb` under the `vex` lock.
The test compiles `rvw/programs/wfi-clock.S` for RV32IM. The Python harness
sets each wake input from stimulus. It does not derive expected values from
DUT data. No backend clock task runs in these tests.

Timer, software and machine external cases pause the clock at a WFI observation.
They assert a pending input during a 100 ns pause. They check retained state
before and after that pause. After restart they check trap cause, EPC region,
MIE clear and the handler's completion store. The masked-global case checks
WFI return with local MTIE enabled and MIE clear, without an interrupt trap.
The tests impose no minimum sleep duration and accept early WFI return.

The S-mode test requests TW=1 and verifies this configuration's legal WARL
readback of zero. It then checks timer wake and interrupt delivery in S-mode.
Zero readback is spec-allowed. Requiring the write to be retained was a test
bug. This test does not claim TW=1 trap coverage.

The U-mode test requires a qualified `RVW_WFI_TRAP_BOUND` in core cycles.
Without it, cocotb skips the test and C3 marks it inconclusive. The old fixed
64-cycle trap deadline was a test bug. The test now accepts WFI completion
before the bound, or an illegal-instruction trap at the WFI PC. It does not
accept a trap from setup code. Do not supply an arbitrary bound to earn coverage.

The source-level U-mode finding remains open. VexRiscv `CsrPlugin` decodes WFI
without a privilege check and stalls it until `wfiWake`, with no timeout in
that path. With S-mode present, an indefinitely stalled U-mode WFI is not
spec-allowed. The previous 64-cycle observation alone did not prove this.
Confirm the core's target privileged-spec version and qualify its timeout
before claiming runtime privilege conformance. No core source is changed here.

The references are the ratified [machine ISA 1.13, virtualization support and
WFI](https://docs.riscv.org/reference/isa/v20260120/priv/machine.html) and
[WARL field rules](https://docs.riscv.org/reference/isa/v20260120/priv/priv-csrs.html).
The timeout is implementation-specific. WFI can complete early, including as
a NOP. TW is WARL; a request for an unsupported value need not be retained.

These are RTL simulation checks. They do not test a physical clock gate,
metastability, debug wake, or clock-domain crossings. The component harness
does not emit C2 or claim a Spike instruction match. The separate opt-in
`rvw/tests/devices/test_wfi_runtime.py` supplies C1/C2 and Spike comparison.
Full #149 acceptance requires the unresolved privilege and reference checks.
