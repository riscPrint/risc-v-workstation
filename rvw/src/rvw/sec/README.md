# Security tests in simulation

`rvw sec` tests digital information flow and microarchitectural leakage.
Timing, caches, speculation, predictors and TLB state are in scope.
Power and electromagnetic leakage are out of scope.
A clean result is `no_leak_observed`. It never means `secure`.
Formal security proofs belong to `rvw formal security`.

## Dynamic information flow

```
rvw sec ift --rtl unit.v --top unit --policy policy.json --stimulus samples.json --out out/ift
```

Policy JSON names `clock`, active-high synchronous `reset`, `sources` and `sinks`.
Sources and sinks name flattened Yosys signals. An internal register can be a source.
A memory is mapped to registers. Name the mapped storage signals as sources.
Bind memory regions and key CSRs to these signals in project data. Automatic address
range decoding is not implemented. For a handshake timing sink, select its valid,
ready or grant signal. For a debug or bus sink, select its observed output signals.
An optional scalar public input `declassifier` permits sink taint while it is high.
This is a sampled release permission. It does not erase taint or prove authorization.

Stimulus is a JSON list of cycles. Every cycle binds every non-clock input to an
unsigned integer. Start with reset high and then release reset. Cycle zero is the
first driven cycle. Sampling occurs after each rising edge and combinational settling.
`--db design.db` maps exact signal names in candidate paths to C6 signal paths.
`report.json` retains policy, sample count, violations and cycles. `results.json`
contains C3 outcomes. MCP tool `sec_ift` uses the same runner.

## Decisions

Reuse the existing Yosys Boolean IFT transform. This supports exported Verilog
from any HDL. A Spinal-only pass would restrict the frontend. The simulation layer
does not change the formal command or its policy. `--mode precise` uses
value-sensitive Boolean transfer functions. This is local precision, not exact
whole-design tracking. `--mode conservative` propagates every gate input taint.
Both modes track mux control and sequential state. Clocks must be public.
Unsupported cells cause an error. Native commands have bounded time limits.

## What this technique can show

A tainted sink identifies potential secret influence under the supplied stimulus.
The result gives a cycle and a structural candidate path. It does not reconstruct
dynamic provenance. A C6 match is name based. It does not establish a complete
source-level path. Reconvergence can cause false alarms in both modes.
There is no proof of whole-core noninterference, declassification authorization,
reset coverage or hardware security. Verilator uses two-state simulation. The
caller must reset all relevant state before observation. No physical model runs.

## Tests

`rvw/.venv/bin/python -m pytest rvw/tests/test_sec.py -q` runs small Verilog designs
with a planted leak and a fixed control. No BOOM simulation is needed.

## Architectural contract pairs

`rvw sec contract --manifest pair.json --out out/pair` runs two independent RTL
cases and reduces a witnessed difference. MCP tool: `sec_contract`.
A manifest declares `contract`, `clauses`, `observations`, `public`, `secrets`
(two different JSON values), `seed`, `instructions`, and `adapter_command`.
The command generates a seeded public ALU instruction list. A project can supply
its own `program` list with loads, branches and transient operations instead.

```
{"contract":"constant-time", "clauses":["pc","memory","branch"],
 "observations":["cycles","cache","branch","tlb","bus"],
 "public":{"reset":"cold"}, "secrets":[0,1], "seed":7, "instructions":16,
 "adapter_command":["python3","adapter.py","{request}","{out}"]}
```

The adapter receives `rvw.sec-case/1` JSON. It must compile and run the program
with its declared secret binding. It writes `response.json` with `complete: true`,
`reset_complete: true`, `reference_c2`, `rtl_c2` and `observations`.
C2 paths are relative to the case output directory. The reference must come from
an independent Spike run or equivalent trusted ISA model. The tool checks
complete C2 traces and architectural agreement for each case before comparison.
Adapters can convert `rvw.probe-events/1` cache, branch and TLB samples into
observation arrays. Keep cycle and bus samples in these arrays when relevant.
The adapter owns reset, probe placement, receiver sampling and ELF generation.

The contract names are `constant-time`, `sandboxing` and
`speculative-constant-time`. Clauses select retired PCs, memory addresses and
branch outcomes. The name records intent. A name alone does not emulate
speculation or prove sandbox access policy. The project program and independent
reference implement those semantics. This flow compares RTL transient samples
within equal architectural traces. It does not infer transient observations
from the reference. This follows the equal-contract-class approach used by
Revizor. It is not an implementation of Revizor, SpecDoctor or TheHuzz.

The reducer deletes instructions and reruns both cases. It keeps a deletion only
when the contract is still equal and the leak persists. `minimize_runs` bounds
trials and defaults to 16. The witness is not necessarily a global minimum.
Missing or mismatched evidence gives `inconclusive`. No eligible comparison also
gives `inconclusive`. Adapter claims and external tool dependencies are trusted.
No native whole-core campaign has been run for this interface.

## Speculative gadget templates

`rvw sec gadgets --out out/gadgets --seed 3` emits RV64 assembly for Spectre-v1,
indirect-target v2, store-bypass v4 and return-predictor patterns. `sec_gadgets`
provides the same MCP interface. Each pattern includes a seeded 256-line receiver.
The receiver stores cycle deltas and sets t6 if a sample is below `--threshold`.
That flag alone is not a leakage verdict. Compare paired receiver arrays and
architectural contracts with `sec contract`. A trained public line can also be fast.

`suite.json` declares the register ABI and required environment hooks. The project
must initialize memory, flush probe lines, train predictor state, arrange delayed
resolution and bind the receiver. V1 needs an index outside the architectural
bound. V4 needs an alias slot that initially points to the secret and is overwritten
with the public pointer. Threshold calibration belongs to the project.

The generated suite expects no leak, including on an in-order core. A speculation
declaration does not make a leak expected or acceptable. Generation is not an
executed self-checking core suite. These templates do not demonstrate that a core
speculates, triggers a gadget, or prevents leakage. Native core execution and
portable training/flush adapters remain open. RISC-V has no universal predictor
training or cache-flush interface for all cores.

## Operand-independent latency

`rvw sec latency --manifest latency.json --out out/latency` measures a synchronous
unit with Verilator. MCP tool: `sec_latency`. Use an exported crypto unit or a
project wrapper that decodes a declared Zkt instruction. The manifest names
`rtl`, `top`, `clock`, active-high synchronous `reset`, `start`, `done`, `operands`,
`max_cycles` and `pairs`.

```
{"rtl":"unit.sv","top":"Unit","clock":"clk","reset":"reset",
 "start":"start","done":"done","operands":["a","b"],"max_cycles":100,
 "declaration":"Zkt project wrapper",
 "pairs":[{"operation":"declared op","a":{"a":0,"b":1,"opcode":3},
                                      "b":{"a":255,"b":1,"opcode":3}}]}
```

Each operand pair binds every data input. Only declared operands can differ.
Public operation selectors must match. Each case resets the unit for two cycles,
pulses start for one cycle and samples the first done after each rising edge.
Different completion cycles are a violation. Missing completion is inconclusive.
The report retains every measured latency, including unresolved operands.

This tests cold, reset unit latency for supplied operands. It does not check
functional crypto results, instruction decode, all possible operand values,
backpressure, warm pipelines or physical leakage. Declaring a Zkt operation is
not evidence that a wrapper implements it. Whole-core retirement timing can be
checked through `sec contract` with a project timing observation channel.

## Isolation across a boundary

`rvw sec isolation --manifest isolation.json --out out/isolation` uses the paired
runner for `pmp`, `epmp`, `register-state`, `predictor-state` or `cache-state`.
MCP tool: `sec_isolation`. Use the contract manifest above with these extra fields:

```
{"isolation_kind":"epmp", "boundary":"M to U", "contract":"sandboxing",
 "contract_start_pc":"0x80001000",
 "policy":{"denied_region":"project secret region", "cleanup":"project rule"}}
```

Supply a project program that sets protection, warms private state, crosses the
boundary and measures the public observer. `program`, `boundary` and `policy`
are required. `contract_start_pc` selects the first retired PC of the public
region in both reference traces. The contract compares that suffix. Every RTL
trace must still match its complete independent reference trace. The adapter
must restrict observation channels to the same public region and confirm reset.

The native fixture checks a private register that affects public latency after
a mode boundary, with a clearing control. It is a small digital state model.
It is not native PMP/ePMP, predictor or cache validation. The tool does not infer
CSR encodings, implement a PMP policy model, verify the selected privilege mode,
or verify that a project flushes all relevant state. The project program and
policy binding must establish these conditions. A missing boundary is an error.

## Critical-register faults

`rvw sec fault --manifest fault.json --out out/fault` reuses `rvw fault` site
selection, single-bit flip planning, C1 injection confirmation and C2 comparison.
MCP tool: `sec_fault`. The manifest declares `db`, `elf`, `critical_registers`
(path globs), `window` (start and end cycles), `samples`, `seed`,
`adapter_command` (argv list), `detections` and `observations` (channel names).
Use absolute adapter paths. Database and ELF paths are relative to the manifest.

The adapter receives the existing `run --fault FILE` interface. It must also
write `security-observations.json` in every run directory. This is an object
with exactly the declared channels, including timing, bus or probe arrays as
required by the threat model. A passing matching C2 trace alone is not enough.

A named declared detection mechanism satisfies the detection check. A generic
failure status without a named mechanism is unresolved. An architecturally
harmless fault also needs identical declared security observations. Changed
observations are a violation. Missing observations, unconfirmed injection and
unresolved faults keep the campaign incomplete. Detection does not prove that
no data escaped before the mechanism fired. Set the project's detection contract
and observation window accordingly.

Native tests use a tiny Verilog key register and parity guard. The planted
unguarded fault changes a debug observation while its synthetic NOP architecture
stays equal. The fixed variant reports a parity detection. This is not physical
fault injection. Multi-bit, clock, voltage, laser and EM attacks are not modeled.

## Suite outcomes and MCP

```
rvw sec suite --report out/ift/report.json --report out/pair/report.json --out out/security
rvw mcp --list
```

MCP tools are `sec_ift`, `sec_contract`, `sec_gadgets`, `sec_latency`,
`sec_isolation`, `sec_fault` and `sec_suite`. Long native operations use MCP jobs.
`sec_suite` collects executed reports into C3 tests. It retains violations when
another technique is incomplete. Generated gadget manifests cannot count as
executed evidence. A partial violation stays incomplete even though it is a
failure. An IFT stimulus with no enabled sink sample is inconclusive.

With `--db`, IFT also uses the existing C6 query engine to resolve structural
source-to-sink dependency paths. Each query records database capture identity.
Unknown or ambiguous names retain an inconclusive path entry. These C6 paths
are structural candidates, not dynamic provenance and not proofs of influence.

C3 `pass` means the declared finite sample met that technique's criterion.
It does not mean secure. Fault checks can satisfy a declared detection contract
without establishing absence of earlier leakage. The suite does not combine
several incomplete techniques into a security proof or a release approval.

## Native runs on a whole core

A project binds its core once in `rvw.sec-core/1` JSON (see `docs/contracts/sec.md`).
The generic harness (`rtl.py`) compiles the core's exported Verilog with a
testbench that owns RAM, in-order bus responses, C2 capture and cycle-stamped
observations. Builds are cached under `RVW_SEC_WORK` (default `~/.cache/rvw/sec`).
`python -m rvw.sec.core_adapter` is a ready `adapter_command` for `sec contract`
and `sec isolation`: it renders the case into a project template (fixed-length
`lui`/`addi` secret setup, so the public instruction stream does not change),
builds the ELF, makes the Spike reference with `rvw cosim generate`, runs the RTL
and writes the observations `cycles`, `retire_cycles`, `dbus_trace`,
`ibus_trace`, `dbus_addresses` and `bus_timing`.

```
rvw sec ift-core --binding core.json --policy memory-policy.json --asm prog.S --out out/ift
rvw sec contract --manifest examples/vexriscv/rvw/sec/constant-time.json --out out/ct
rvw sec isolation --manifest examples/vexriscv/rvw/sec/isolation-leaky.json --out out/iso
rvw sec spec-suite --binding core.json --template spec.S --out out/spec
```

`ift-core` maps the core to a Yosys gate netlist (`async2sync`, X and dangling
bits to zero) and adds the Boolean taint shadow. RAM keeps a taint mask per
word: a load returns it and a store writes the stored data's taint. A policy
names `memory_regions` (ELF symbol or address, size), register `sources` (a
netname such as a CSR register) and `sinks` (top-level outputs, each with an
optional `when` valid signal). The first tainted sink sample, its cycle count and
the last retired PC are reported up to the retirement of the `tohost` store.
MCP: `sec_ift_core`, `sec_spec_suite`.

`spec-suite` runs four RV32 gadgets (`v1` forward branch, `v2` indirect jump,
`rsb` return, `v4` store bypass) under `speculative-constant-time`. The secret
is x7. Architectural code only does register arithmetic with it. The wrong-path
load uses a secret-derived address. The receivers are the paired data bus trace
and retirement timing. There is no cache receiver on these cacheless cores.

### Probe and bus observations

The harness also samples probe events. It finds SpinalProbes wires
(`rvwprobe__KIND__NAME__FIELD`) in the top module and the binding's declared
`events` (kind, name, `valid` and `fields` on internal signals). It writes
`probe-events.jsonl` (`rvw.probe-events/1`) per run, cut at the `tohost` store
retirement like C2, so `rvw probes convert` reads it. Branch `semantics` and
other elaboration metadata come from the binding's `probe_meta`. Observation
channels: `branch_events`, `cache_events`, `tlb_events`, `probe_events` (all
non-counter events), `probe_counters` (totals in the window) and
`bus_handshakes` (cycle of every command and response on every bus).
Event cycles are relative to the window start.

On VexRiscv the example `ProbePlugin` gives branch, flush, retire and counter
probes. On VexiiRiscv the binding declares the upstream Whiteboxer
prediction-learn port as a `branch` event. The VexRiscv stream converts to
`rvw.bp-events/1` with matching C2 order. The VexiiRiscv learn port fires
before commit (4 events for 3 retired branches in one run), so that converter
refuses it. It still serves as an observation channel. Neither example core has caches or
a TLB, so `cache_events` and `tlb_events` are only tested with synthetic sites.
With `probe-ct.json` (a loop of divides): VexRiscv gives `no_leak_observed` on
cycles, handshakes, branch events and counters. VexiiRiscv differs in cycles,
handshakes and branch-event timing, reduced to one `remu`.

### Results on the example cores (2026-11-13, Verilator 5.049, Spike)

Each row is one command on RTL generated from the pinned example revisions
(`examples/*/rvw/sec/build-rtl.sh`). The RTL traces matched Spike in every
compared case (all C2 fields on VexRiscv; `pc` and `insn` on VexiiRiscv).

| Technique | Core | Case | Result |
|---|---|---|---|
| `ift-core`, secret memory words | VexRiscv | `ct-xor` (load key, XOR, store) | `no_leak_observed`, 70 cycles |
| `ift-core`, secret memory words | VexRiscv | `leak-branch` | violation: fetch address tainted at cycle 11, data bus at 15 |
| `ift-core`, secret memory words | VexRiscv | `leak-index` (table lookup) | violation: data bus address tainted at cycle 13 |
| `ift-core`, secret CSR `mscratch` | VexRiscv | `csr-ct` / `csr-index` | `no_leak_observed` / violation at cycle 10 |
| `ift-core`, secret memory words | VexiiRiscv | `ct-xor` | `no_leak_observed`, 184 cycles |
| `ift-core`, secret memory words | VexiiRiscv | `leak-branch` / `leak-index` | violation at cycle 58 (fetch) / 69 (LSU address) |
| `contract` constant-time | VexRiscv | div, divu, rem, remu, mul, mulh, mulhu | `no_leak_observed`: every divide takes 34 cycles |
| `contract` constant-time | VexiiRiscv | same program | **violation**, reduced to one `remu x13, x6, x7`: 14 cycles for 7 % 3, 38 cycles for 0x7fffffff % 1. The full program took 113 against 209 cycles. |
| `isolation` M/U | VexRiscv `rv32imu` | U-mode `ecall`s, constant-time M handler with a `div` on the secret | `no_leak_observed`: 68 cycles per call for both secrets |
| `isolation` M/U | VexRiscv `rv32imu` | handler loop count from the secret (control) | violation: 48 against 84 cycles per call, reduced to `add; ecall` |
| `spec-suite` | VexRiscv | v1, v2, rsb, v4 | `no_leak_observed` for all four |
| `spec-suite` | VexRiscv patched | same | violation in `dbus_trace` for v1, v2 and rsb; v4 `no_leak_observed` |

The VexiiRiscv result is a true positive: its radix-2 divider (`DivRadix2`)
skips zero quotient bits, so divide and remainder latency depends on the
operands. Do not use VexiiRiscv division on secrets in constant-time code
with this configuration. VexRiscv's `MulDivIterativePlugin` divider has a fixed
count. The patched VexRiscv lets flushed loads issue on the data bus
(`examples/vexriscv/rvw/sec/leaky-transient-load.patch`). It exists only to show
that the speculative receiver path detects a transient secret-dependent access.
On both unpatched in-order cores, wrong-path loads never reach the bus.

### What each native technique can and cannot show

- `ift-core` shows that a secret word or register influenced a sink in this
  run, with the cycle. It cannot show which source statement caused it. A clean
  run covers only this program and these sinks. Gate-level taint can over-taint
  at reconvergence. Async reset is modeled as synchronous; X becomes 0.
  A core that keeps CSRs in RAM (VexiiRiscv) has no single CSR source name.
- `contract` shows a timing or bus difference between secrets with equal
  architectural traces. A clean result covers only the given secrets and program.
- `isolation` with `observer_mode` compares only what the lower privilege
  retires and sees. It does not check PMP, which these cores do not have.
- `spec-suite` gadgets are short; the receivers are the bus trace and timing.
  A cacheless core has no cache receiver. A clean result does not prove that the
  core never speculates.

## Remaining integration work

The default pair generator is a small seeded ALU grammar. Broader instruction,
memory and privilege fuzz grammars need project bindings. Gadget generation
still needs executed core suites. PMP/ePMP, predictor/cache cleanup and declared
Zkt decoding need independent project models and native core evidence. IFT
memory regions need mapped signal declarations; dynamic source-level taint
provenance is not implemented. These limits remain open work.

## Generated RTL reset and unknown constants

The Boolean IFT shadow pass accepts public rising-edge synchronous state.
Other reset/clock cells return `unsupported` with a shared elaboration fix hint
before native compilation. Set SYNC reset in the project entry, then rebuild
simulation and SpinalDB. Do not change only the database configuration.

X and Z constants represent either Boolean value. Their representative value
is zero and their taint is one. This can add findings. It cannot establish
absence of leakage through an unknown constant. It does not model electrical
high impedance. Both precise and conservative modes retain this uncertainty.
