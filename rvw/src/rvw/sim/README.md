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


## Accellera UVM components

`rvw regress uvm --out NEW_DIRECTORY --seeds 3 --json` runs the pinned
Accellera UVM library with native Verilator timing and coverage.
See [the UVM suite](../../../../Uvm/README.md) for the pin, licence checks,
machine lock command, conformance boundary and remaining DPI/VIP gaps.
It writes standalone C3. It does not implement C1 or earn C4 acceptance.

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

