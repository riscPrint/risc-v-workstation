# Accellera UVM subset

This component suite runs the full, unmodified Accellera UVM 2020.3.1 package
on native Verilator with `--timing --assert --coverage`. It uses
`UVM_NO_DPI`. It does not replace the UVM library with a local subset.
Only the behavior checked by the tests is qualified.

## Build and run

Install Verilator, a C++ compiler, make, and an SMT solver supported by
Verilator (Z3 for the example). Install `rvw` as described in
[the setup guide](../docs/BRING_YOUR_OWN_CORE.md).

From the workstation checkout, run:

```sh
scripts/with-lock.sh boom nice -n 10 rvw/.venv/bin/rvw regress uvm \
  --verilator /path/to/verilator --seed 1 --seeds 3 --out /tmp/uvm-new --json
```

The output directory must be new. The default suite is this checkout's
`Uvm/tests`. Use `--suite PATH` if the source files are in another location.
The timeout applies separately to compilation and each simulation.
Compilation uses two compiler jobs. Runtime uses one simulator thread.

The runner fetches the source archive from the official
[Accellera release](https://github.com/accellera-official/uvm-core/releases/tag/2020.3.1).
Use `--archive PATH` for an offline copy. Both paths require the same hash.
The pin is commit `78c06547a2a0a29b3dc9dcafae62b75b2ff61544`.
The archive SHA-256 is
`9ee918499a92518f8f7c202c5f8a38b8a0c83d4eba3bedd7890bfa3ed023d1e4`.
The runner also checks the pinned hashes of `LICENSE.txt` and `NOTICE.txt`.
It retains both files in the extracted source tree. The upstream licence is
Apache-2.0. No upstream source is copied into this repository. This check
does not select a licence for the workstation project (#37).

## Conformance boundary

| C3 test ID | Checked behavior |
|---|---|
| `phases_config_factory_tlm` | Build, connect, run, check and report phases; timed run objection; virtual interface through config DB; factory creation; sequencer/driver handshake; analysis port to subscriber |
| `constrained_random` | Forty item randomizations; legal opcode and aligned address constraints checked before directed overrides; randomized data and source; changed data; unsatisfiable constraint must fail |
| `functional_coverage` | SV covergroup sample; opcode and address coverpoints; cross; `get_inst_coverage()` must return 100%; independent eight-bin bitmap must also be full |
| `tlul` | Four-word RAM; Get and PutFullData; aligned 32-bit transfers; one outstanding request; source echo and D opcode/data checks |
| `rvfi` | Synthetic load observation: valid, order, instruction, memory address/data and destination data checked against an independent memory model |
| `ral_frontdoor` | Generated 32-bit RW registers; TL-UL frontdoor write/read, automatic prediction and checked mirror |
| `interrupt_debug_pins` | Four interrupt level bits; halt/resume requests; acknowledgement and halted state on a timed pin fixture |
| `ral_fault_detection`, `pins_fault_detection` | Separate corruption runs must stop with their expected diagnostic |
| `rvfi_fault_detection` | A separate run corrupts destination data. It must fail with the specific RVFI mismatch and must not reach the completion marker |

The sequence starts with four writes and four reads to cover each address.
It then sends 32 constrained random transactions. Four RAL transfers follow.
The passive monitor samples
the accepted request and its registered response. The scoreboard owns a
separate, zero-initialized memory model. Expected values never come from DUT
responses.

The design is a RAM with a synthetic `lw x1, offset(x0)` observation port.
It is not a RISC-V CPU. Its observation port is not a complete RVFI interface
or a C2 trace. The scoreboard does not establish ISA conformance. Masked
writes, subword accesses, denied/corrupt responses, backpressure, bursts,
multiple outstanding requests and multi-hart behavior are outside this suite.

## Results

The runner writes standalone C3 `rvw.results/1` through `rvw regress uvm`.
Each seed gets seven normal entries and three fault-detection entries.
A normal pass requires all expected test markers, exactly one completion
marker, no UVM errors or fatals, and simulator exit 0. The negative test needs
a nonzero exit and the expected RVFI fatal. A crash alone cannot pass it.
The test sets the UVM fatal action to `UVM_DISPLAY | UVM_STOP`.
The default UVM fatal action calls `$finish`, which can return exit 0.
Timeouts, build errors and incomplete output are errors with inconclusive
evidence. Logs, compile commands, seed, simulator version, archive hash and
source hashes stay in the output directory. Verilator also writes
`coverage.dat` there.

These component results do not implement C1 ELF execution, C4 acceptance,
C8 complete replay identity, caching or tier scheduling. C3 explicitly marks
source identity incomplete. The runner uses process groups to stop child
tools on timeout or cancellation. It does not infer full language support
from a successful library compile.

## Tests

```sh
nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/test_uvm.py -q
scripts/with-lock.sh boom nice -n 10 env RVW_UVM_ARCHIVE=/path/to/pinned.tar.gz \
  RVW_UVM_VERILATOR=/path/to/verilator rvw/.venv/bin/python -m pytest \
  rvw/tests/test_uvm_native.py -q
```

The native test runs seeds 1, 2 and 3. A missing archive setting skips that
test. A skip is not evidence of UVM support.

## Decisions and limits

Accellera DPI is disabled. Component-name regex validation is skipped by upstream UVM.
UVM HDL read, deposit, force, release and polling, and the
DPI regex implementation are not qualified. The pinned DPI C++ source needs
a portable header include on macOS and a Verilator HDL backend. A simulator
extension is not established as necessary for every disabled feature.
A backend implementation and passing tests must determine the remaining
VPI gaps. No substitute backend or silent backdoor success is supplied.

RAL backdoor, factory overrides, field automation, UVM callbacks, phase jumps,
AXI and full CPU VIP are not tested. The additions below define the bounded
RAL, pin-agent and CPU replay checks. Advanced constraints and coverage
constructs are not qualified by the simple expressions in this suite.
Only the installed version and the exact tests that pass can establish
support. Simulator versions are recorded at runtime. The upstream
`DEVIATIONS.md` still applies.

## Register models and pin agents

`rvw regress uvm-ral --map MAP.json --out ral.sv` generates a UVM register
block from a validated `rvw.soc/1` map. It preserves absolute addresses,
register widths, access rights and declared resets. Each register has one
full-width field. The supported field policies are RO, WO, RW, RC and W1C.
RC requires read-only access. W1C requires read-write access. The generator
refuses combined side effects. Unknown reset values have no reset prediction.
The map uses little-endian byte addressing and a four-byte frontdoor bus.
A wider register uses multiple bus beats. Field slices and backdoor paths
are not generated.

The component suite now generates its RAL from `tests/registers.json`.
It connects a `uvm_reg_adapter` to the TL-UL sequencer. It checks frontdoor
write/read, automatic prediction and a checked mirror on the RAM fixture.
Only 32-bit RW frontdoor operation is qualified by this native fixture.
RO, WO, RC, W1C and other widths have generator tests; these tests do not
qualify a physical register implementation.

`tests/controls.sv` provides a sequencer, driver and monitor for interrupt
levels and halt/resume request pins. Its sequence drives bits 3, 7, 9 and 11,
then halt and resume. The monitor checks level propagation, acknowledgement
and halted state on a timed fixture. These are pin-agent conformance tests.
They do not establish CPU interrupt acceptance, RISC-V Debug Module support,
JTAG DMI, abstract commands or debug-mode architectural comparison.

The runner also performs RAL and pin corruption runs. Each must stop on its
own diagnostic with a nonzero exit. These runs must not reach completion.
Each seed produces seven normal C3 entries and three fault-detection entries.

## CPU retirement scoreboard through Spike DPI

Use an existing C1 run from a core adapter. Enable `--rvfi-trace` when you
run its ELF. Then run:

```sh
scripts/with-lock.sh vex nice -n 10 rvw/.venv/bin/rvw regress uvm-cpu \
  --run-dir /path/to/c1-run --elf /path/to/program.elf \
  --platform examples/vexriscv/rvw/platform.json \
  --archive /path/to/pinned.tar.gz --verilator /path/to/verilator \
  --out /tmp/uvm-cpu-new --json
```

To run the adapter and check its capture in one command, replace
`--run-dir` with `--adapter /path/to/run.sh --config NAME --lock LOCK`.
Set the adapter's environment as its project requires. `--seed` and
`--max-cycles` control that C1 run. The adapter owns its simulation lock.
The runner uses `--lock` for DPI compilation and replay. Do not hold that
same lock around the full adapter command. An adapter failure or timeout
cannot produce a passing scoreboard result.

Build the current Spike shim with `Cosim/build.sh` first. Use
`RVW_SPIKE_SHIM` to select another matched build. The runner reuses the
cosim input capture and manifest checks. The native bridge checks the
embedded ABI, source hash and build identity before it creates Spike.
Accellera's own DPI remains disabled. The scoreboard uses a separate DPI
bridge. It does not require an Accellera HDL/VPI backend.

The UVM monitor publishes captured C2 retirements to an analysis subscriber.
The subscriber calls Spike through DPI once per retirement. The bridge checks
instruction and next PC, instruction bits, privilege, integer destination,
source values, memory address, byte masks, masked memory data, trap flag and
memory-fault flag. Reference operands and effects come from Spike. A second
run corrupts next PC. It must stop on `SPIKE_MISMATCH` with nonzero exit.

This is offline capture replay through `rvw regress uvm-cpu`. It does not
place UVM inside the core's RTL simulation. It does not add UVM jobs to
`rvw regress run` tiers or establish C4 gate acceptance. C1 status must be
pass. Its ELF hash and retirement count must agree with the captured ELF
and C2. C2 must start at order zero, have no gaps, and end with pass.
A matching prefix cannot pass. Source identity stays incomplete in C3.

The initial CPU profile supports scalar C2 version 1, one RAM region,
trap misalignment policy, and pre-step privilege reporting. It uses strict
comparison without counter, MMIO or CSR synchronization. It refuses MMIO,
nonzero IRQ events, trap side records, handler/halt observations, FP writes,
C2 version 2, multi-hart and extended CSR/fault observations. Instruction
classes that Spike can execute and C2 can represent use the same comparison;
there is no load-only or opcode allowlist. This does not establish complete
ISA coverage. CPU interrupt/debug execution and a full ISA campaign remain
open under #296.

## Python environment path

See [pyuvm](pyuvm/README.md) for the optional pyuvm 4/cocotb 2 base environment,
ordered scoreboard, bounded CPU memory model, retirement comparator wrapper and
RAL frontdoor/backdoor adapters. The native RTL memory fixture checks eight
transactions and all declared operation/address bins. CPU reference connections
and project-specific instruction, interrupt and debug agents remain required.
