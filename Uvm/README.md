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
| `rvfi_fault_detection` | A separate run corrupts destination data. It must fail with the specific RVFI mismatch and must not reach the completion marker |

The sequence starts with four writes and four reads to cover each address.
It then sends 32 constrained random transactions. The passive monitor samples
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
Each seed gets five normal entries and one fault-detection entry.
A normal pass requires all expected test markers, exactly one completion
marker, no UVM errors or fatals, and simulator exit 0. The negative test needs
a nonzero exit and the expected RVFI fatal. A crash alone cannot pass it.
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

DPI is disabled. UVM HDL read, deposit, force, release and polling, and the
DPI regex implementation are not qualified. The pinned DPI C++ source needs
a portable header include on macOS and a Verilator HDL backend. A simulator
extension is not established as necessary for every disabled feature.
A backend implementation and passing tests must determine the remaining
VPI gaps. No substitute backend or silent backdoor success is supplied.

RAL frontdoor and backdoor, factory overrides, field automation, UVM
callbacks, phase jumps, register prediction, AXI, interrupt/debug agents,
and full CPU VIP are not tested. Advanced constraints and coverage
constructs are not qualified by the simple expressions in this suite.
Only the installed version and the exact tests that pass can establish
support. Simulator versions are recorded at runtime. The upstream
`DEVIATIONS.md` still applies.
