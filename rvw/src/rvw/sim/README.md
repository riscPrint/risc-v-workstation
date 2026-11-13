# Native simulation

`backends.py` declares the guarantees of the native adapter profiles. Use
`require(backend, features)` before a run. Unknown backends and unknown or
unsupported features are errors. A profile describes this invocation, not every
feature of the simulator. It does not certify an installed version.

Verilator uses two-state values. Icarus preserves four-state X/Z values.
Neither profile guarantees pessimistic X propagation, complete SystemVerilog,
concurrent SVA or coverage. Foreign interfaces listed in the profile describe
native support. This adapter uses VPI only. Other native backends are refused
until they have a profile and conformance tests.

See [architectural injection](INJECTION.md) for project state maps, readback,
raw FP values and the RV32IM bootstrap API. This API is separate from live snapshots.

Use `rvw sim reverse-step adapter.json --snapshot A.json --snapshot B.json
--current 500 --target 450 --max-seconds 30 --out restored.json` for checkpoint
replay. MCP: `sim_reverse_step`. See [reverse execution](REVERSE.md) for port
requirements, history limits and the current native qualification limit.

## External timing replay handoff

`rvw sim timing-handoff request.json --capabilities adapter.json` checks a
project's external gate-netlist/SDF handoff. MCP: `sim_timing_handoff`.
The result is `declared_compatible`. It is not native annotation evidence.
Both documents must list supported/requested cells, delay constructs, timing
checks, unknown-value behavior and SDF corners. Unsupported requests fail.

`rvw.timing-request/1` includes `top`, `netlist`, `sdf`, `cell_libraries`,
`cells`, `delays`, `timing_checks`, `unknown_behavior` and `corner`.
Paths resolve beside the manifest. Inputs must be nonempty. Unknown behavior
is `four-state` or `two-state`. Corner is `min`, `typ` or `max`.
`rvw.timing-capabilities/1` includes `simulator`, `version`, `cells`, `delays`,
`timing_checks`, `unknown_behavior`, and `corners`. Inventories are project
and adapter declarations. The tool does not infer complete cell inventories.
The report includes exact input sizes and hashes.

External native adapters can implement `timing.TimingPort`. `replay` captures
all declared input bytes before calling the adapter. Its `run_timing` must
consume those bytes, refuse ignored annotation and return a native C1 outcome.
Compilation alone is refused as an outcome. A replay result always reports
`physical_signoff: false`. Cell-library, delay and timing-check qualification
belongs to the external adapter. No bundled gate-level backend or physical
validation is supplied by this interface.

## Profile recorded build and run costs

Use `rvw sim profile --result RUN/result.json --result OTHER/result.json
--build-profile threads-4 --out NEW_REPORT.json`. MCP: `sim_profile`.
The command reads C1 and reports elaboration, combined native/setup, aggregate
model compile and execution time. It derives kHz and instructions/s from
recorded counters and execution time. Missing Scala-only compilation and peak
RSS measurements remain null. Failed and inconclusive run status is retained.
The report does not qualify correctness or compare treatments.

`--build-profile` prints a proposed `SPINAL_VERILATOR_FLAGS` setting. It does
not apply it or classify recorded runs under it. Profiles cover default,
two/four threads and output splitting. Existing native identity validation
still applies to any later run. Use `speed-sweep` and `speed-compare` for
execution and qualified paired comparisons. Hierarchy bridge access, captured
PGO reuse and an Arcilator C1 engine remain unsupported. The report lists PATH
discovery as `installed` or `not_installed`. This does not validate tool
versions, lowering or runtime behavior. No installer or backend is supplied.

## Cocotb component suites

Install the optional dependency with `cd rvw && uv pip install -e '.[cocotb]'`.
Install native Icarus (`iverilog` and `vvp`) or Verilator, make and a C++ compiler.
Run `rvw regress cocotb manifest.json --out NEW_DIRECTORY --seed 1 --json`.
The output directory must not exist. `--timeout` sets a wall-clock budget in
seconds for compilation and simulation together (default 120).

Example manifest:

```json
{
  "schema": "rvw.cocotb/1",
  "name": "counter",
  "backend": "icarus",
  "top": "CounterUnit",
  "sources": ["rtl/CounterUnit.v"],
  "test_module": "test_counter",
  "python_paths": ["."],
  "requires": ["clock", "timer"],
  "clock": {"signal": "clk", "period_ns": 10},
  "reset": {"signal": "reset", "active": 1, "cycles": 2}
}
```

Paths resolve from the manifest directory. `sources` is nonempty. `python_paths`
is optional. It adds directories to Python's import path. Tests can import
reusable Python testbench packages. `requires` is optional and must contain
only feature names from the selected profile. Unknown fields are errors.
Signal bindings stay in the manifest. Each test calls
`await rvw.sim.bench.start(dut)` after it sets its other input defaults.
The helper starts the clock, holds reset for the requested falling edges, and
releases reset on a falling edge. Without a clock it does nothing. Cocotb
cleans up the clock task at the end of each test. Cocotb receives the recorded
seed and seeds Python's random module.

The adapter runs the cocotb Python runner in a separate process group. Timeout
or cancellation stops its child tools. Verilator builds use two compiler jobs.
The adapter enables immediate assertions for Verilator and `-g2012` for Icarus.
A requirements error happens before the output directory or build exists.

Outputs are standalone C3 `results.json`, raw `cocotb.xml`, `request.json`,
`run.log`, and the native `build/` files. The log records native simulator and
cocotb version messages. C3 carries the profile, seed, input hashes, timeout,
artifact paths and replay arguments. A fresh directory prevents stale XML.
A missing, empty or invalid XML file, a skipped test, a timeout, or a successful
XML report with a failed worker exit is an error. A cocotb failure is `fail`.
Exit codes are 0 for all tests passed, 1 for test failures and 2 for errors.

## Decisions and limits

This is a component suite entry point under `rvw regress`. It does not implement
C1 ELF execution, `regress run` tier scheduling, caching, history, MCP or C4 gate
acceptance. C3 readers can load its standalone output. C4 must not accept it
as an ELF regression: ELF and adapter identity fields are absent.

Cocotb and the simulator retain their own language limits. The adapter does not
infer requirements from RTL. Test authors must declare semantic needs. It does
not add X pessimism, SVA, coverage or waveform flags. Generated RTL must exist
before the run. Compile order follows `sources`. Python imports outside the
listed directories, include files, native libraries, and environment inputs are
not fully captured. Input hashes do not establish C8 completeness or a hermetic
replay. Source Git provenance is not inferred from generated RTL.

Run `python -m pytest rvw/tests/test_cocotb_native.py -q` from the checkout for
small timer, clock/reset, settled register, X/Z and two-state conformance cases.
Missing optional tools cause skips. These cases qualify only the exercised
behavior on the installed versions. See the Spinal-generated counter and
VexRiscv unit examples in `examples/vexriscv/cocotb`.

C1 native adapters use a separate `riscvsim-verilator` invocation profile. It
supports two-state values, clocks and generated immediate assertions. It does
not promise cocotb callbacks, four-state values, SVA or coverage semantics.
Set `[core] backend = "riscvsim-verilator"` and a suite's `requires = ["clock"]`.
The runner checks all suite requirements before input capture or adapter launch.
A suite with requirements must select a known profile. Old projects without
requirements can omit the profile. Direct RiscvSim shell entry points also check
comma-separated `RISCVSIM_REQUIRES` before launch output, locks or native tools.
Requirements are author declarations. They are not inferred from RTL.


## Accellera UVM components

`rvw regress uvm --out NEW_DIRECTORY --seeds 3 --json` runs the pinned
Accellera UVM library with native Verilator timing and coverage.
See [the UVM suite](../../../../Uvm/README.md) for the pin, licence checks,
machine lock command, conformance boundary and remaining DPI/VIP gaps.
It writes standalone C3. It does not implement C1 or earn C4 acceptance.

## Compare simulation speed

`rvw regress speed-compare --pair BASE1 CAND1 --pair BASE2 CAND2 ... --out report.json`
compares at least five pairs of C1 files. Each file must record a conclusive
pass, a native build identity, positive counters, a serial first attempt and
at least one second in `details.execution_s`. Use `--min-seconds 10` for long
workloads. Warm the model first. Do not include warmup results in the pairs.
Keep the workload, preset, seed, memory timing and trace options fixed.
Interleave baseline and candidate runs. Reverse their order in alternate pairs.
Use distinct result paths and simulation execution `run_id` values. Run one simulation at a time under the core lock.

The command validates C2 records and requires an end event, matching C1
counters, matching ELF and seed, and identical trace events across all pairs.
Native build identities may differ between baseline and candidate. Each
side must keep one identity. A missing trace or any difference gives exit 3.
This is simulation result equivalence. It is not an ISA oracle check.
Run the reference-model checks separately before adopting an option.

The report records every C1 path and hash, C2 hash and native build identity.
`speedup` is the geometric mean of paired baseline/candidate execution times.
`speedup_ci95` is a percentile bootstrap interval over pairs (10000 resamples;
fixed seed 1). `retain` requires its lower bound to exceed 1 and raw C2 byte identity.
`trace_bit_identical` reports that check. `sim_khz` reports each treatment's
geometric mean rate and marginal bootstrap 95% interval. This threshold
checks timing noise only. The interval assumes independent pairs. Shared-host
load, order bias and autocorrelation can invalidate that assumption. Do not
use five short samples to claim precise speedups. Report host load and run
order with measured results. The command does not tune or change defaults.

Use separate reports for each preset and workload. The input files must remain
available to inspect a report. Reports belong outside the repository.

### Verilator experiment protocol

Sweep `SPINAL_VERILATOR_FLAGS='--threads N'` for N = 1, 2, 4, then test output
splitting with `--output-split 10000 --output-split-cfuncs 500`. Test only one
change at a time. Keep `RISCVSIM_MAKE_JOBS` fixed. Native identity captures these
options. Keep an option only after complete result equivalence and a measured
benefit on the target design. More threads can reduce throughput.

Thread PGO requires a training build with `--prof-pgo`, a representative run
that writes `profile.vlt`, then a rebuild with that file as a Verilator input.
Keep source, flags and profile hashes. Treat `PROFOUTOFDATE` as a failed
experiment. The current native identity collector refuses profile file inputs;
these runs cannot earn conclusive C1 evidence or a retained speed option yet.
Do not bypass that check. Hierarchical builds require declared partition
boundaries and a separate build integration. They are not enabled by this tool.

`ccache` affects native build time, not steady-state simulation throughput.
Measure cold and warm builds separately. The current collector refuses opaque
compiler wrappers and `OBJCACHE`; do not use an inconclusive run as speed evidence.
See [Verilator simulation guidance](https://verilator.org/guide/latest/simulating.html)
and [Verilator options](https://verilator.org/guide/latest/exe_verilator.html).

### Checkpoints and other simulators

The existing replay descriptor starts from reset. It cannot resume live state.
Adding `--savable` alone is insufficient: the Spinal native bridge needs save
and restore calls, and the Scala scheduler, memory, devices, monitor, RNG and
pending stimulus need one versioned snapshot. External effects must be refused.
Fresh-process suffix equivalence on VexRiscv and bounded BOOM remains required.
No live checkpoint result is supplied by `speed-compare`.

CIRCT's [circt-verilog](https://circt.llvm.org/docs/Tools/circt-verilog/)
accepts Verilog input. An Arcilator evaluation also needs a native driver for
the lowered design and the same memory, reset and retirement observations.
Parsing or compiling generated Verilog is not result equivalence. An absent
tool or unsupported lowering must be reported as inconclusive. Backend capability
profiles remain separate from this comparison command.

### Run a thread sweep

Use `rvw regress speed-sweep --adapter /path/to/run.sh --elf /path/to/long.elf
--config PRESET --lock vex --threads 2 4 --repeats 5 --min-seconds 10 --out NEW_DIR`.
Choose the core's machine lock. The command warms each native model, then runs
serial baseline/candidate pairs in alternating order. Each run uses a fresh
process, seed 1, fixed memory latency zero and C2 tracing. Use `--seed` and
`--max-cycles` to set the workload bounds. The baseline uses one thread.
The command appends `--threads N` to inherited `SPINAL_VERILATOR_FLAGS`.
Remove any inherited thread option first. Other inherited build settings stay
fixed and remain subject to native input capture.

Each launch holds the selected lock and uses `nice -n 10`. `--timeout` bounds
the entire launch, including the lock wait and compilation (default 1200 s,
maximum 1800 s). Timeout or cancellation stops its process group. A failure
stops the sweep. `sweep.json` retains run order, commands, flags, launch times,
host, CPU count, file hashes and completed comparisons. Its status stays
inconclusive until every requested comparison passes. It does not change
simulator defaults. The sweep covers run throughput only. Build phase timing,
peak RSS, partitioning, PGO and ccache require separate experiments.


## Native HDL testbenches

Use `rvw regress backends --hdl --json` to list HDL invocation profiles.
Use `rvw regress hdl MANIFEST --out NEW_DIRECTORY --json` to run one testbench.
`--backend NAME` selects a profile per run. Requirements still apply after an
override. These profiles are separate from the cocotb profiles.

| Profile | Values and scheduling | Supported subset |
|---|---|---|
| `icarus` | Four-state HDL events | X/Z values, delays, immediate assertions |
| `verilator-timing` | Two-state HDL events with `--timing --assert` | Delays, edge controls, nonblocking assignments, fork/join, immediate assertions |
| `ghdl-yosys-icarus` | Icarus events on a synthesized VHDL netlist | Synthesizable VHDL-2008 components in a Verilog/SystemVerilog testbench |

No profile enables coverage or foreign interfaces. Concurrent SVA, full
SystemVerilog, pessimistic X propagation, VHDL event semantics and VHDL
nine-value logic are unsupported requirements. The mixed path converts VHDL
with `ghdl --synth --std=08 --out=verilog`. Yosys checks the hierarchy and lowers
processes. Icarus compiles the resulting netlist with the HDL testbench. This
path needs native GHDL synthesis support and Yosys. It does not use a VPI bridge.
Synthesis can change unknown values. The mixed profile thus refuses
`four_state` and `xz_values` even though Icarus runs the final netlist.

Example `rvw.hdl/1` manifest:

```json
{
  "schema": "rvw.hdl/1",
  "backend": "icarus",
  "top": "tb",
  "sources": ["xreset.sv"],
  "requires": ["four_state", "xz_values", "hdl_delays"]
}
```

For mixed synthesis, also set `vhdl_sources` to an ordered list of VHDL files
and `vhdl_top` to their component entity name. Use `requires: ["mixed_synth"]`.
The testbench `top` and `vhdl_top` must be simple HDL identifiers. Paths resolve
from the manifest directory. Unknown fields and requirements are errors before
output creation or tool launch. Missing tools also cause a preflight error.
The compiler checks language support on the installed version before simulation.
Profiles state adapter limits; they do not certify arbitrary language constructs.

The testbench must use `$fatal(1, ...)` on a failed check. It must print one
exact `RVW_PASS` line only after all checks finish. Then it must call `$finish`.
Exit zero alone cannot pass. Native error diagnostics, a missing or duplicate
marker, a failed tool or a timeout produce `error` and CLI exit 2. A pass gives
exit 0. `--timeout` bounds version probes, synthesis, compilation and simulation
together. Cancellation stops the process group. Builds use one compiler job.
The output directory must be new. It contains `results.json`, the resolved
request, separate stdout/stderr logs for each command, and generated files.

See [the examples](../../../../examples/sim-semantics/README.md) for commands
and conformance cases. Four-state accuracy here means Icarus language X/Z
semantics, including X optimism in conditional statements. It does not mean
pessimistic X propagation. The comparison case checks four settled values in
one X-free counter, not equivalence of arbitrary designs. This runner does not
execute C1 ELF runs, change the RiscvSim backend, or earn C4 gate acceptance.
Hashes cover listed source files, not transitive includes, memory images,
libraries or all environment inputs. Replay is not hermetic under C8.


`rvw regress uvm-ral` generates UVM register models from `rvw.soc/1`.
`rvw regress uvm-cpu` checks completed C1 captures through a UVM analysis
subscriber and the native Spike DPI bridge. See [the UVM guide](../../../../../Uvm/README.md)
for the strict profile and the offline replay boundary.


Persistent regression workers use separate process groups. See
[the regression guide](../regress/README.md) for defaults and failure recovery.
Each worker has a serial server and reuses its compiled model. This does not
provide live snapshots or prove reset equivalence for an adapter.

## Native snapshot envelope API

`rvw.sim.checkpoint` provides `save`, `load` and `restore` for adapter authors.
The adapter must provide a `SnapshotPort` and stop simulation advancement at a
quiescent boundary. The port saves native model bytes and eleven explicit harness
components: scheduler, clock, memory, pending transactions, RNG, devices,
interrupts, monitors, RVFI state, stimulus position and counters. Empty inventories use empty
containers. A missing component is an error.

The `rvw.native-checkpoint/1` envelope binds these bytes to SHA-256 identities
for RTL, native build, harness and stimulus. Load validates the whole envelope
before calling the adapter. The adapter then checks its own state format before
it installs state. Discard the model after any restore exception. Save requires
a new file. External effects, such as host sockets, are unsupported.

This is an adapter API. The SpinalHDL 1.15.0 native interface has no model
save/restore methods. No bundled adapter implements this port yet. The envelope
tests use a fixture port. They do not establish native checkpoint equivalence.
From-reset replay descriptors remain a separate format and operation.

A native smoke test uses a direct Verilator `--savable` accumulator. It saves
the model, clock time, PRNG, memory word and monitor counter at cycle 8. A fresh
process restores these values. Its remaining 12 samples must equal the
uninterrupted suffix. This does not qualify the Spinal bridge or a RISC-V core.

## Live checkpoint commands

`rvw sim checkpoint adapter.json --cycle 100 --out snapshot.json` advances a
project port to a stopped boundary. Use `--instruction N` instead for a retired
instruction boundary. The port must stop at exactly that count. Capture refuses
a different count. `rvw sim resume adapter.json snapshot.json --out NEW_DIR`
creates a fresh port, validates the identity envelope, restores and finishes.
MCP tools are `sim_checkpoint`, `sim_resume` and `sim_suffix_check`.

The `rvw.snapshot-adapter/1` project manifest contains `module` (a Python file),
`identity_files` (nonempty ordered file lists for `rtl`, `native_build`, `harness`
and `stimulus`), and optional `options`. Paths resolve beside the manifest.
This is executable trusted project code. Its `create(options)` returns a
`SnapshotPort` with `advance(unit, target)`, `position(unit)`, `finish(out)` and
`close()`. Units are `cycles` and `instructions`. `finish` must create a fresh
C1/C2 run directory. The adapter owns native stepping and all state inventories.
The manifest and module bytes also contribute to harness identity. List all
transitive native inputs. This declaration does not infer a complete inventory.

Run `rvw sim suffix-check ORIGINAL_C2 RESUMED_C2 --position BYTE_OFFSET` after
resume. The offset comes from the captured writer. Both traces must include a
C2 header and end event. Exact prefix and nonempty suffix bytes must match.
This check proves byte equality only. Run C1 terminal checks and independent
ISA checks separately. No bundled Spinal port is qualified by these commands.

## Native Arcilator model library

Install the pinned CIRCT release outside the repository:

```sh
scripts/install.sh --with-arcilator
scripts/install.sh --with-arcilator --check
```

The release is `firtool-1.163.0`. Archive SHA-256 values are pinned for macOS
ARM64, macOS x64 and Linux x64. The default location is
`~/.cache/rvw/circt/firtool-1.163.0`. `RVW_CIRCT` selects another installation.
The check rejects a different CIRCT version or missing native tools.
Unsupported hosts fail. No source build or simulator fallback occurs.

`rvw.sim.native_models.Model` compiles captured RTL with `circt-verilog`,
Arcilator and LLVM `llc`. It exposes packed ports through 65,536 bits through the
emitted state layout. Project adapters own clocks, reset, memory, interrupts,
C1 terminal predicates and C2 observation. The same interface has a Verilator
backend for paired native runs. Both start with zero state and then use the
project reset sequence. There is no four-state or HDL-delay guarantee.
The build record captures source, compiler, engine and shared-library hashes.
It is not a complete C4 reuse identity. Do not use it for gate acceptance.

The [VexRiscv probe](../../../../examples/vexriscv/README.md#arcilator-and-verilator-c1c2-probe)
provides bounded C1/C2 evidence on real captured core RTL. The native scalar
regression also checks reset and 40 seeded register updates against an
independent arithmetic expectation. This is a cycle model API, with no timing,
foreign-function, coverage, native checkpoint or BOOM qualification.

The [whole-core VexRiscv reset probe](../../../../examples/vexriscv/README.md#whole-core-four-state-reset-probe)
runs captured Verilog through Icarus with an initial X reset interval. It
separates active retirement unknowns from inactive memory-data unknowns.
A native injected-output-X test checks that active unknowns cannot pass.
This is a bounded project probe. It adds no pessimistic X-propagation guarantee.

## Captured scalar build profiles

The native scalar model accepts an optional `rvw.native-build-profile/1` file.
It supports explicit thread counts, hierarchy boundaries, a private ccache and
Clang compiler PGO capture/reuse. `rvw.common.capture.Capture` freezes profile,
RTL, training ELF, SDK settings, make rules and reused profile data. Bindings
reject changed inputs. Outdated and unprofiled compiler diagnostics remain
errors. The scalar namespace is `scalar-native-profile-v3`. No C4 model-cache
reuse is enabled. The production Spinal collector keeps its existing refusals.

The [VexRiscv campaign](../../../../examples/vexriscv/rvw/profiles/README.md)
records native build/setup time, execution plus trace time, child-process RSS,
compiler-cache hits and complete C2 equality for eight real profiles. It includes
a compiler-profile capture and reuse. `rvw sim profile` reports these recorded
fields when present. It does not apply profiles or qualify a runtime winner.

## Native packed ports and public waves

The native model API accepts packed input and output widths through 65,536 bits
on both Arcilator and Verilator. `Model(..., wave=PATH)` records public ports
in a two-state VCD. Timestamps count model evaluations. They do not describe
physical time. Internal signal waves remain outside this API.
See [the native comparison](../../../../examples/vexriscv/rvw/native-wide/README.md)
for wide-register controls, complete whole-core C2 checks and measured engine
throughput. Wave capture adds cost and is excluded from untraced comparisons.
