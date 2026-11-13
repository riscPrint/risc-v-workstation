# Security tests in simulation

`rvw sec` tests digital information flow and microarchitectural leakage.
Timing, caches, speculation, predictors and TLB state are in scope.
Power and electromagnetic leakage are out of scope.
A clean result is `no_leak_observed`. It never means `secure`.
Formal security proofs belong to `rvw formal security`.

## Techniques at a glance

Real results come from RTL generated from the pinned VexRiscv and VexiiRiscv
example revisions (details in the sections below).

| Technique | Command | It can show | It cannot show | Real result |
|---|---|---|---|---|
| Unit IFT | `ift` | a secret input or register reaches a sink of a small unit under given stimulus | whole-core behavior; source-level provenance | seeded Verilog units |
| Whole-core IFT | `ift-core` | a secret memory word or CSR reaches a bus address or handshake in one program, with the cycle; which RAM words received tainted data | leaks outside the chosen sinks and program; exact causes (gate taint can over-taint) | both cores: constant-time XOR clean; secret branch and secret table index flagged; `mscratch` binding on VexRiscv; cached VexRiscv: the same two results through the cache refill bus |
| Contract pairs | `contract` | a timing, bus or probe difference between two secrets with equal architectural traces, reduced to a short witness | absence of leaks for other secrets or programs | VexiiRiscv `remu` latency depends on operands (14 vs 38 cycles); VexRiscv divide is fixed (34); cached VexRiscv: a secret-indexed table lookup found through cache hit/miss events of public probe loads, a constant-time lookup clean |
| Isolation | `isolation` | timing a lower privilege observes across a privilege switch (`observer_mode`); with `pmp`, what a denied access exposes | ePMP; state cleanup outside the observed channels | VexRiscv M/U: constant-time handler clean; secret-dependent handler flagged (48 vs 84 cycles). VexiiRiscv `rv32imasu` U/S/M with Sv32: constant-time handlers clean across U-M, U-S and S-M, secret-dependent handlers flagged; a secret-selected S-mode page read is visible to U through TLB walks. VexRiscv with PMP: a denied U-mode load never reaches the bus; a dependent load sees no secret (pairs and IFT clean) |
| Speculative self-tests | `spec-suite` | a wrong-path access with a secret-derived address on the bus or in timing | that a core never speculates; cache receivers on cacheless cores | both in-order paths clean; a patched VexRiscv that issues flushed loads is flagged for v1, v2 and rsb |
| Campaign | `campaign` | new leak signatures from generated and mutated pairs, deduplicated | coverage of the whole input space; a clean campaign is bounded by its budget | VexiiRiscv: `remu` and `div` signatures in 24 pairs; VexRiscv: none in 24 pairs |
| Model pre-check | `model-check` | predicted timing leakage of a planned unit before RTL | transient, cache or predictor leaks; exact cycle counts | predicts the direction of both cores' divide results |
| Unit latency | `latency` | operand-dependent latency of a unit for given operands | crypto correctness, warm pipelines | seeded units |
| Critical faults | `fault` | a single-bit upset in a declared register changes security observations, or is detected | multi-bit, clock, voltage or physical faults | seeded units |

## Dynamic information flow

```
rvw sec ift --rtl unit.v --top unit --policy policy.json --stimulus samples.json --out out/ift
```

Policy JSON names `clock`, active-high synchronous `reset`, `sources` and `sinks`.
Sources and sinks name flattened Yosys signals. An internal register can be a source.
A memory is mapped to registers. Name the mapped storage signals as sources.
Bind memory regions and key CSRs to these signals in project data. For whole cores,
`ift-core` binds RAM words and CSRs automatically (below). For a handshake timing sink, select its valid,
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
`python -m rvw.sec.core_adapter` is a native whole-core adapter for this
interface (see "Native runs on a whole core").

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
speculates, triggers a gadget, or prevents leakage. These RV64 templates need a
project receiver. For RV32 cores bound with `rvw.sec-core/1`, `spec-suite` runs
executed gadgets with bus and timing receivers. Portable training and flush
adapters remain open. RISC-V has no universal predictor training or cache-flush
interface for all cores.

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
runner for `pmp`, `epmp`, `register-state`, `predictor-state`, `cache-state` or `tlb-state`.
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
refuses it. It still serves as an observation channel. The cached VexRiscv
configuration (`core-cached.json`, `rv32im_cached`) has cache probes (`CacheProbes`):
I$ and D$ accesses with hit, lookups, refill beats, fills, evictions and counters.
`cache_events` keep the address, hit and write fields and drop `data`: line
contents are architectural data, and the fetched lines hold the secret setup
immediates (the first constant-time run differed only there). Cache refill ports
use `burst: true` buses (see `docs/contracts/sec.md`).
With `probe-ct.json` (a loop of divides): VexRiscv gives `no_leak_observed` on
cycles, handshakes, branch events and counters. VexiiRiscv differs in cycles,
handshakes and branch-event timing, reduced to one `remu`.

### Automatic secret bindings

An `ift-core` policy can name secrets by their project meaning:

- `{"soc_region": "keystore"}` in `memory_regions`, optionally with
  `offset`/`size` or a `register` of an MMIO region, resolves through the
  project's `rvw.soc/1` map (`--soc`, or `soc` in the core binding).
- `"csrs": ["mscratch", "0x341"]` checks each name or address against the
  pinned CSR catalog and finds the one design netname that stores it (name ends
  in `_<csr>`; flop outputs and internal names win over copies and ports). A
  binding `csr_signals` map overrides the search. No match or several matches
  is an error that lists the candidates.

Taint is kept per RAM word. The report lists the resolved `csrs` and
`memory_regions` and `tainted_memory`: the number of tainted words at the end
and the words outside the secret regions that received tainted data.

Results (`ift/auto-policy.json`: the SoC `keystore` region, plus `mscratch` on
VexRiscv; the same programs on both cores):

| Core | Program | Result | Tainted RAM outside the secrets |
|---|---|---|---|
| VexRiscv | `keystore-ct` (keystore XOR mscratch, stored) | `no_leak_observed`; `mscratch` resolved to `CsrPlugin_mscratch` | the 4 output words |
| VexRiscv | `keystore-index` (table lookup by a keystore word) | violation: data bus address at cycle 17 | none |
| VexiiRiscv | `keystore-ct` | `no_leak_observed` | the 4 output words |
| VexiiRiscv | `keystore-index` | violation: LSU address at cycle 75 | none |

On VexiiRiscv, `csrs` gives "no storage signal": its CSRs live in a RAM.


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
| `isolation` pmp | VexRiscv `rv32imu-pmp` | U-mode load of a PMP-denied keystore word, then a load indexed by it | `no_leak_observed`: access fault (cause 0xd) as in Spike; the denied load is absent from the bus trace; 30 cycles for both secrets |
| `ift-core` keystore | VexRiscv `rv32imu-pmp` | same sequence, keystore words as secrets | `no_leak_observed`; no tainted data left the keystore |
| `spec-suite` | VexRiscv | v1, v2, rsb, v4 | `no_leak_observed` for all four |
| `spec-suite` | VexRiscv patched | same | violation in `dbus_trace` for v1, v2 and rsb; v4 `no_leak_observed` |
| `isolation` U-M | VexiiRiscv `rv32imasu` | `isolation-um-ct.json`: U ecalls, constant-time M handler on `mscratch` | `no_leak_observed`: 97 cycles per call for both secrets |
| `isolation` U-M | VexiiRiscv `rv32imasu` | `isolation-um-leaky.json`: handler loop count from the secret (control) | violation: 124 against 232 cycles per call, reduced to `addi; ecall` |
| `isolation` U-S, Sv32 | VexiiRiscv `rv32imasu` | `isolation-us-*.json`: delegated U ecalls, S handler on `sscratch` from a supervisor-only page | constant time: `no_leak_observed` (246 cycles); loop: violation in `cycles`, `retire_cycles` and `tlb_events` timing (300 against 516) |
| `isolation` S-M, Sv32 | VexiiRiscv `rv32imasu` | `isolation-sm-*.json`: S-mode observer, M handler on `mscratch` | constant time: `no_leak_observed` (226 cycles); loop: violation (280 against 496) |
| `isolation` tlb-state, Sv32 | VexiiRiscv `rv32imasu` | `tlb-us-leaky.json`: the S handler reads the user page that secret bit 0 selects; U then loads `page_b` and `page_a` | **violation** in `retire_cycles`, `tlb_events`, `bus_handshakes`: the U load of the page the handler did not read walks the page table (2 PTE reads, 25 cycles), the other hits (5 cycles) |
| `isolation` tlb-state, Sv32 | VexiiRiscv `rv32imasu` | `tlb-us-ct.json`: the handler reads both pages | `no_leak_observed` (53 cycles) |
| `contract` constant-time, cache channel | VexRiscv `rv32im_cached` | `cache-index.json`: a load from table line `secret & 32`, then public probe loads of both lines; window from the first probe | **violation** in `cache_events`, `probe_counters`, `cycles`, `retire_cycles`: for secret 0 the probe of line 1 misses and line 0 hits (8 cycles); for 32 the reverse (19 cycles, one fill) |
| `contract` constant-time, cache channel | VexRiscv `rv32im_cached` | `cache-ct.json`: both lines loaded, the value selected with a mask; whole program | `no_leak_observed` (214 cycles, 3 D$ misses each) |
| `ift-core`, secret memory words | VexRiscv `rv32im_cached` | `ct-xor` / `leak-index` with `ift/cache-policy.json` | `no_leak_observed`, 247 cycles / violation: D$ refill address tainted at cycle 167, then the fetch command at 178 (the secret decides hit or miss, so the stall timing) |

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
  retires and sees. The TLB case shows that VexiiRiscv keeps S-mode TLB entries
  for user pages across `sret`; RISC-V does not require a flush there, so this is
  expected behavior, and software that must hide such accesses needs
  `sfence.vma` or separate ASIDs. Both are a true positive of the channel, not a core bug.
- `spec-suite` gadgets are short; the receivers are the bus trace and timing.
  A cacheless core has no cache receiver. A clean result does not prove that the
  core never speculates.

## Leakage campaigns

`rvw sec campaign --manifest campaign.json --out out/campaign [--resume]` runs a
coverage-guided loop of contract pairs through the same case adapter. MCP:
`sec_campaign`. Each iteration:

1. selects a contract from `contracts` (round robin);
2. takes a corpus program and mutates it (insert, delete or replace an
   instruction; a branch stays with its label), or generates a new one from the
   RV32IM grammar (`classes`: alu, alui, mul, div, load, store, branch);
3. mutates the secret pair (bit flip of one secret register, or new values with
   boundary values such as 0, 1, 0x7fffffff, 0x80000000);
4. runs the pair without reduction. New coverage keys from the first case's
   observations (per-instruction retirement latency, bus trace length, probe
   branch outcomes, probe counter values) add the program to the corpus;
5. reduces a violation with the paired reducer and files it under its root-cause
   signature: the reduced program's sorted mnemonics and the differing channels.

The grammar keeps secrets (x6, x7) out of load and store addresses and branch
conditions, so the architectural contract normally holds and a difference is
microarchitectural. `budget` bounds pairs and seconds. `state.json` is written
after each pair; `--resume` continues until the budget (raise it in the
manifest to continue a finished campaign). Outputs: `report.json` (`rvw.sec/1`),
`results.json` (one C3 `fail` per signature, or one `pass`/`error`) and
`report.md`. A clean campaign is `no_leak_observed` for the pairs it ran.

Results with `examples/*/rvw/sec/campaign.json` (both contracts, seed 11,
24 pairs each, RTL from the pinned revisions):

| Core | Outcomes | Coverage keys / corpus | Signatures (reduced witness) |
|---|---|---|---|
| VexiiRiscv | 18 `no_leak_observed`, 6 violations | 24 / 14 | `remu` (`remu x15, x7, x5`, 3 pairs, both contracts), `div` (`div x10, x7, x10`, 3 pairs) |
| VexRiscv | 24 `no_leak_observed` | 47 / 18 | none |

The first VexRiscv campaign found a harness bug: RVFI reports a byte store's
data replicated across the word. Store data now compares on its written byte
lanes, as `rvw cosim` does.


## Model pre-check before RTL

`rvw sec model-check --manifest model-precheck.json --out out/model` runs the
contract pair on the trace-driven OoO model (`rvw/src/rvw/ooo/`) instead of
RTL. MCP: `sec_model_check`. Each secret's program runs on Spike; its C2 trace
drives the model description named by `model` (`rvw.arch-core/1` or a plain
`ooo` table). `operand_latency` states the planned unit behavior per class:
`fixed` (`latency`), `quotient_bits` (`base` + `per_bit` × quotient bit length,
a divider that skips zero quotient bits) or `early_out` (`short` when the chosen
operand fits in `width` bits, else `long`). Rules read the operands from the
reference trace. Equal architectural contract traces with different predicted
cycles are a predicted violation.

Results with the example in-order model descriptions (`examples/*/rvw/arch/own.json`)
and the constant-time divide program of `constant-time.json`:

| Manifest | Planned rule | Predicted cycles (7/3 vs 0x7fffffff/1) | Prediction | RTL result |
|---|---|---|---|---|
| `vexiiriscv/rvw/sec/model-precheck.json` | divide `quotient_bits`, base 4 | 28 vs 57 | violation | violation (`remu`, 14 vs 38 cycles) |
| `vexriscv/rvw/sec/model-precheck.json` | divide `fixed` 34 | 56 vs 56 | `no_leak_observed` | `no_leak_observed` (34 cycles each) |
| `vexiiriscv/rvw/sec/model-precheck-mul.json` | multiply `early_out`, 16 bits, 1 or 4 cycles | 25 vs 33 (dependent `mul` chain) | violation | no RTL: a planned unit |

The direction of both RTL results is predicted. The cycle counts are not: the
model is a timing approximation. In the multiply case, an unrelated `mul`
whose result is used late showed no difference (fetch-bound), so a planned
early-out unit leaks only where its latency is on the critical path.

The pre-check shows only what the model and the stated rules contain. The model
is committed-path only: it cannot predict transient (speculative) leakage,
cache or predictor state leaks need the component models and secret-dependent
addresses, and a rule is a design statement, not a measurement. Confirm every
prediction on RTL with `sec contract` when RTL exists.


## Remaining integration work

- The cached VexiiRiscv configuration is not bound: its LSU L1 is write-back,
  so the `tohost` store does not reach the bus, and its write bus sends
  multi-beat bursts. VexRiscv `rv32im_cached` is the cached core here.
- Whole-core IFT on a cached core is costly: 250,514 cells and a 109 MB shadow;
  the cold Yosys and Verilator build took 339 s, above the 120 s flow budget.
  A run after the build cache is warm finishes within the budget.
- The VexRiscv `rv32imu-pmp` variant has a NAPOT-only PMP (upstream
  `PmpPluginNapot`, 32-byte granularity). The general `PmpPlugin` makes a
  combinational loop with `DBusSimplePlugin`. ePMP and supervisor isolation
  need another configuration.
- VexiiRiscv has no RVFI. Its C2 check compares `pc` and `insn` only, and its CSR
  storage is a RAM, so CSR secrets cannot be bound there.
- The campaign grammar is RV32IM without CSRs, privilege changes or loops.
- The model pre-check is committed-path only.
- Dynamic source-level taint provenance is not implemented.
- Whole-core IFT ties X constants to zero, as the two-state Verilator run does.
  An X constant is then a public constant. The unit `ift` pass instead treats X
  as unknown and tainted (next section).

## Generated RTL reset and unknown constants

The Boolean IFT shadow pass accepts public rising-edge synchronous state.
Other reset/clock cells return `unsupported` with a shared elaboration fix hint
before native compilation. Set SYNC reset in the project entry, then rebuild
simulation and SpinalDB. Do not change only the database configuration.

X and Z constants represent either Boolean value. Their representative value
is zero and their taint is one. This can add findings. It cannot establish
absence of leakage through an unknown constant. It does not model electrical
high impedance. Both precise and conservative modes retain this uncertainty.

Generated mapped projects include `rvw/sec/flow.S`. Run it with the generated
core binding and flow policy using `sec ift-core --asm rvw/sec/flow.S`.
Precise mode is the default. Use `--timeout 110` for a finite preparation budget.
The progress report records netlist, shadow, compile and simulate phases.
A timeout returns an inconclusive partial report. Cell and byte counts explain
preparation cost. They are not a latency or leakage result.

### C1 adapters and RV64 pairs

Use `python -m rvw.sec.c1_adapter --binding core.json --template case.S REQUEST OUT`
as the `adapter_command` of an existing contract manifest. This reuses a C1
project at RV32 or RV64. It does not need the mapped security RTL harness.
The binding and timing scope are in `docs/contracts/sec.md`, under C1 pair adapter.
The VexiiRiscv example supplies `rvw/sec/core64-c1.json`, `case64.S` and
`constant-time64.json`. Run the manifest with `rvw sec contract`.

Each pair side must pass a complete strict Spike comparison before timing is
eligible. The pair compares actual case-window retirement times. Its scoped
trace ends at the observed passing store. The full raw trace is retained and
strictly checked first. A fixed public setup length prevents operand magnitude
from changing the setup instruction count. A reported timing violation is one
witness under this contract. A pair without a violation is not a security proof.
