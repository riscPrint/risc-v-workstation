# Live scalar CPU environment

`rvw_cpu_if.sv` is the project wrapper boundary. The project maps its scalar
RVFI signals to the 19 values listed in that interface. The monitor samples
at falling edges. The scoreboard checks contiguous order, then calls the
same independent Spike DPI step comparator used by captured replay. It
counts a check only after the comparator succeeds.

Compile the interface before `rvw_cpu_pkg.sv`. Link `Uvm/spike_bridge.cpp`.
Generate `spike_effect.h` from the current shim fields. Initialize Spike
before `run_test`. Supply a matched, captured ABI 6 shim and the same ELF
image as the DUT. See `../examples/cpu/run.py` for the setup. Set `vif` in
`uvm_config_db` for the environment and monitor. The project owns core pins,
clock generation, reset polarity conversion, bus handshakes and test end.

`cpu_env` contains the live RVFI monitor, Spike subscriber, instruction/CSR/
interrupt/exception observation bins, and shared byte memory. Both memory
ports use one `cpu_memory` object. Project protocol adapters call `access`
after accepting a transfer. The task supplies bounded random response delay,
byte enables, range checks and an optional fetch-error address. This is a
normalized service. It is not an AXI, OBI or TileLink wire implementation.
Protocol wire agents remain under `Uvm/vip/`.

`cpu_control_sequence` supplies reset, interrupt-level pulses and debug-request
pulses. Project virtual sequences can call these tasks. The clock comes from
the project wrapper. The strict Spike profile rejects handler-entry and halt
retirements. Pin stimulus does not establish interrupt or debug architectural
correctness. CSR instructions step through Spike. Set `state_valid` to check all 32
architectural GPRs after retirement. Set `csr_count` and the CSR address/value
arrays to check up to eight CSR snapshots through Spike. An unavailable CSR
is an explicit error. Project wrappers must supply committed state. Native
qualification covers GPR snapshots and read-only `misa` snapshots on the
small fixture. Other CSR behavior remains unqualified. These limits must remain explicit in test plans.

The Python equivalents are `rvw.sim.cpu_env.CpuMemory`, `CpuScoreboard`,
`CpuCoverage` and `monitor`. They use the same memory/error policy and scalar
observation fields. Supply a captured `rvw.cosim.spike.Spike` instance as the
reference. It steps independently. Project cocotb agents own the memory bus
pins. `monitor` takes a project binding map with `clock`, `reset_n`, `valid`,
and a `fields` dictionary from observation names to DUT signal names. The
optional pyuvm environment can use these services without SV class support.

## Bounded fixture

Run from the checkout with the optional UVM dependencies installed:

```sh
nice -n 10 rvw/.venv/bin/python Uvm/examples/cpu/run.py \
 --shim Cosim/build/librvw_spike.so \
 --archive /path/to/pinned-uvm.tar.gz --out /tmp/live-cpu-new
```

Build the matched shim first with `Cosim/build.sh`. The fixture builds a
six-instruction RV32I_Zicsr ELF, loads its bytes into memory, inserts seeded fetch
response delays, and compares all six live retirements through Spike DPI.
It runs seeds 1 and 3. Separate runs corrupt destination data, a GPR snapshot and a CSR snapshot. Each must stop
on `SPIKE_MISMATCH`. The fixture supports ADDI and read-only MISA only. It is not VexRiscv,
full ISA qualification, interrupt/debug qualification or C4 gate acceptance.
The runner writes the existing C1/C3 formats. Their source identity
remains incomplete. The existing VexRiscv captured-replay path is unchanged.

## Cocotb fixture

After the native example has built its ELF, set `RVW_CPU_ELF` to that ELF.
Set `RVW_CPU_SHIM` to the matched shim. Set `RVW_CPU_PLATFORM` to
`Uvm/examples/cpu/platform.json`. Use absolute paths. Then run:

```sh
nice -n 10 rvw/.venv/bin/rvw regress cocotb \
 Uvm/examples/cpu/cocotb.json --out /tmp/cpu-python-new --timeout 90 --json
```

The wrapper exposes the same small ADDI core without SV UVM classes. The
Python scoreboard compares six live retirements against Spike. The optional
`Uvm/pyuvm/cpu_env.py` wraps these services as a pyuvm environment. Its project
configuration supplies the DUT bindings, reference, ELF and expected count.

Normal native runs also emit complete scalar C2 traces. Merge their observed
instruction, CSR and trap bins with the existing coverage command:

```sh
rvw cov functional /tmp/live-cpu-new/seed-1/rvfi.jsonl \
 /tmp/live-cpu-new/seed-3/rvfi.jsonl --out /tmp/cpu-coverage.json --json
```

Coverage counts describe five ADDI instructions and one MISA read per seed. Unhit CSR, interrupt and
exception bins remain unhit. No coverage closure is claimed.

## Program and control sequences

`cpu_env.vseqr` connects shared memory, the retirement scoreboard and the
control sequence to a virtual sequencer. Start `cpu_program_sequence` on it.
Set `byte_image` to the ELF-derived byte image. Set `retirements` to the
expected bounded count. The sequence loads memory, resets the DUT and waits
for that count. `max_cycles` bounds the wait. The live fixture uses this path.

`cpu_random_control_sequence` generates seeded interrupt levels and debug
request pulses. Set `allowed_irqs` from project data. Set `count` and
`max_gap` to positive bounds. Each IRQ level stays within the declared mask.
The Python `CpuControls` service takes project callbacks for reset, IRQ,
debug and cycle waits. `RandomControlSequence` starts it through the pyuvm
virtual sequencer. Supply `controls` in the Python environment configuration.

The program test owns its run-phase objection. A project can run control
sequences alongside a program. The strict bridge still refuses handler-entry
and halt retirements. Random pin stimulus does not establish architectural
interrupt or debug behavior. The separate control fixture checks propagated
levels, acknowledgement and halt/resume state for six directed transfers,
16 random transfers and one final resume.

## VexRiscv project binding

The [VexRiscv example](../examples/vexriscv/README.md) connects the shared
Python CPU environment to real VexTop instruction, data and RVFI pins.
It uses seeded bus delays and independent Spike step comparison.
Program completion requires a checked `tohost` pass store. Its separate
corruption mode changes next PC and must fail. Use the `vex` lock for runs.

## Catalog-derived CSR qualification

`rvw.uvm.csr_sequence.CsrQualification` loads the checks worker's
`rvw.csr-selection/1` catalog selections or explicit `rvw.csr/1` models.
`CsrQualificationSequence` wraps it for the Python virtual sequencer.
Pass a project async `execute(address, transaction)` callback. It must
execute a CPU CSR instruction, wait for completion, and return `trap`
and the instruction's pre-write `read_data`. It must not access a bus
register in place of a CSR instruction.

The sequence checks reads against the independent model. For CSRs with
project `assembly_safe=true`, it adds zero, all-ones, walking-one and seeded
random writes with checked readback. It restores the declared reset value.
Unknown-reset safe CSRs receive an explicit initialization write before the
first read. Other unknown resets are refused. Absent CSRs require a trap.
The generator never infers write safety or reset values from the catalog.

Unit tests qualify the generator and comparator. The live VexRiscv binding
does not yet implement the instruction-execution callback. Native CSR,
architectural interrupt and debug qualification remain open. The selected
VexTop has no debug port. No pin-only test establishes debug architecture.

## Architectural event service

`rvw.uvm.cpu_events.CpuEvents` synchronizes separate project trap pulses with
independent Spike steps. Supply the selected XLEN and platform IRQ causes.
For an interrupt, also supply the independently driven IRQ mask at the
accepted boundary. An unrequested cause fails. Trap cause and tval must
match Spike before the next retirement is checked. No DUT register value
is copied into the reference.

The debug service compares acknowledged halt/observe snapshots with Spike's
debug state, DPC, DCSR, step bit and PC. Call it at a synchronized retirement
boundary. Do not call it merely because a request pin was asserted.
Resume is explicitly unsupported. These services have unit tests.
Their presence does not qualify a project's interrupt or debug wiring.

## Native qualification matrix

See [the measured matrix](../QUALIFICATION.md). On 2026-11-13, the SV CPU
fixture built once on Verilator 5.049 in about 109 seconds. Its two normal
runs and three corruption checks passed. The runner now accepts
`--build-timeout` with a 600-second default. The run timeout remains short.
This is the ADDI/MISA fixture. VexRiscv SV CPU qualification remains open.

Refresh the matrix after native runs:

```sh
rvw uvm qualification --cpu-results /path/to/cpu/results.json \
 --probes /path/to/probes/probes.json --out Uvm/QUALIFICATION.md
```

Use `Uvm/probes/run.py` to refresh the engine probes. SV transition bins
had a runtime gap and an ignored-feature warning on Verilator 5.049.
Use the live pyuvm observed-bin path and `rvw cov functional` as the
coverage workaround. The constrained Python example also supports the
UCIS round trip. None of these paths grants credit for unobserved bins.
