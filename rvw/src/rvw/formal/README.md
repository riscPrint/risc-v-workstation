# rvw formal

`rvw formal bmc` checks assertions from reset. `from-sim` checks them from a VCD or FST
state. `xprop` checks whether unknown state can reach selected signals. See
[SpinalChecks](../../../../SpinalChecks/README.md) for commands and limits.

By default, sequential flows require one rising-edge clock and synchronous state controls.
BMC also supports the explicit sampled event model below. Asynchronous

Assertion flows require one rising-edge clock and synchronous state controls. Asynchronous
reset/load/set/clear controls and latches are refused. A result applies only to the selected depth,
input ties, assumptions, and reset settings. Missing replay state starts free and can cause
spurious failures. Exit 0 means `pass`. Other written results exit 1. Invalid input exits 2.

## Decisions

- Xprop validates `--filter` before elaboration. A malformed regex exits 2 with
  the filter and parser error. MCP reports that input error. No result is written.
- Each flow copies RTL, include files, checks JSON and replay VCD/FST before the first
  probe. `inputs/original/` holds the shared `Capture.file` copies. `inputs/frontend/` holds RTL copies
  whose literal include paths point to copied includes. Nested includes, absolute paths
  and symlink targets are copied. Missing or ambiguous includes, macro-computed include
  paths and file-reading system tasks such as `$readmemh` are refused. Comments and string
  literals do not count as task calls. A macro-built file read is refused by the frontend
  dependency check below. This conservative scan also checks inactive branches, so their
  include files must be available.
- Input capture keeps `..` until after symlink resolution. The selected lookup path,
  resolved source, literal symlink targets, byte count and hash come from the capture record.
  `result.json` includes that record as `input_capture`. Later source edits and link changes
  cannot redirect the proof.
- Every flow captures Yosys, SymbiYosys, the selected solvers and replay converters before
  elaboration. Reachability also pins Yices. Subprocesses use absolute command bindings.
  SymbiYosys gets explicit Yosys, SMTBMC, witness and selected ABC paths. Solver lookup
  uses private command bindings and the saved environment. The supported oss-cad-suite
  launchers retain their runtime settings but keep these bindings first on PATH, including
  the Python launcher. Each command binding restores the caller's captured Python
  environment before dispatch, then the release launcher applies its own settings.
  Unknown SMTBMC shell launchers are refused.
- `Capture.tool` requires a successful `--version`. `yosys-smtbmc`, `yosys-witness` and
  `yosys-abc` do not provide it. Local adapters report the captured content hash for these
  commands. Their underlying files and detected release payloads also get byte and metadata
  checks. The shared API has no option for a tool with another version interface.
  `tools`, `tool_bindings` and `input_capture` use start-of-command capture identities.
  No version command runs after the proof. Before publication, tool verification checks
  hashes, inode identity and change timestamps. Replacement or edit-and-revert produces
  `unknown` with an `input_not_captured:tool:...` cause. Missing tools refuse the command.
- Supported proof engines are `smtbmc` with Yices, Z3, Bitwuzla, Boolector, CVC4, CVC5
  or MathSAT, and `abc`. `smtbmc:abc` is refused before proof, including in portfolios
  and with extra options. The installed Yosys 0.64+174 ABC SMT parser crashes on an
  ordinary counter. The refusal names the captured Yosys version and ABC hash.
  This engine remains unsupported on other releases until it is validated.
  `abc:bmc3` requires a sequential model. Optimization can remove all state, even
  from clocked RTL. If ABC reports a combinational network and the run errors,
  the command refuses with exit 2 and no `result.json`. The message directs the
  user to rerun with `--engine smtbmc:yices`. No proof or pass is inferred from
  that ABC error. A portfolio can still earn a pass through another engine.
  Other engines refuse capture because their executable dependencies are not defined here.
  No formal result is cached.
- Replay converts its sealed state VCD to FST with the pinned converter before Yosys
  loads it. This prevents an internal converter lookup from changing the selected tool.
- The first frontend run reports its file dependencies with Yosys `-E`. Every file it reads
  must be a copied input. A missing or unsupported report, or a read of any other file
  (also one built by a macro), causes exit 2 with no `result.json`. That run applies the
  proof's defines and writes one RTLIL model after `hierarchy -check -top` and `proc`.
  Port and state-control checks describe that model. Clock and target probes, replay
  state loading, undriven-bit handling and the proof all read that same model.
  Later probes do not preprocess live RTL again.
- `result.json` records `input_snapshot.files` and `input_snapshot.artifacts`.
  Each file records its original lookup path, resolved target, copied path and SHA-256
  from the captured bytes. Rewritten frontend copies also record their paths and SHA-256
  values. Artifacts record the model, generated wrapper and replay proof inputs, each hashed
  once before a tool reads it. The run does not hash its private copies again: it owns
  `--out` under its lock (C8 threat model). A result applies to these copied bytes. Edits
  to live inputs after the copy do not change the proven design. A new run is needed to
  check those edits.
- All three flows check state cells in every elaborated module after `hierarchy -check -top`
  and `proc`, before `prep`, flattening, ties or state loading can remove them. The check
  uses the proof's defines. By default, async flip-flops, latches and unsupported state cell types,
  including fine-grained gate cells, cause exit 2 with no `result.json`. A tied inactive
  reset or unused state does not bypass this check. Asynchronous memory reads remain
  supported; memory async reset ports must be tied to zero. `rvw cov prove` uses the same
  classification (`async_state_problems` in `common.py`). `multiclock off` cannot model
  state events between clock edges, so converting asynchronous state with `async2sync`
  cannot earn a pass.
- Xprop runs `setundef -undriven -undef` after flattening and before X instrumentation.
  Unwritten registers, undriven wires and undriven bus bits become explicit X values.
  Real inputs keep their input status. Driven flip-flops keep Yosys xprop's initial-state
  model: a bit without a known initializer starts X until a write defines it. Reset and
  initial values still define state where the RTL supplies them.
- BMC and replay use two-state formal values. An undriven bit can take either value;
  these flows do not prove that a signal is X-clean. Replay state missing from the waveform
  remains free, including registers with RTL initializers. Use xprop to check X propagation.
- Port direction, width and signedness come from Yosys JSON after `hierarchy -check -top`
  and `proc`, in the first elaboration with the proof's defines (`SYNTHESIS` for xprop).
  Wrappers keep all elaborated input bits free, except explicit ties and clock/reset controls.
  Packed dimensions and integer types use their full bit count. Port offsets and ascending
  ranges are normalized at instance connections, which preserve bit order. Unreadable metadata,
  failed probes, multi-bit clock/reset ports and inout ports are refused.
- Xprop target widths also come from Yosys JSON after flattening and exposure. No Verilog
  text parser sets proof widths. The remaining Verilog text reader maps failed assertions to
  source/check labels only. RTLIL readers count assertions, report replay state coverage, and
  change memory INIT values for the explicit replay memory mode. They do not infer port types.
- Failure mapping first matches the solver's full path to a copied RTL file. A basename
  maps only when it names one copied file. An ambiguous basename leaves the failure's
  module, check and source unset. Summary and engine failures are merged by full path
  and line, so one file cannot hide another file's failure at the same line.
- Failure cycles use the first elaboration's property metadata. A known rising-edge
  assertion has `cycle = replay_offset + step - 1`. Unclocked properties, missing metadata
  and mixed property types on one source line have `cycle: null`. The solver step remains.
- Replay removes design register and memory initial values before loading the waveform.
  It also removes design time-zero assumptions. Current Yosys represents these as zero-width
  triggered `$check` cells. Older Yosys uses `$initstate` and `$assume`. The flow handles both
  before it creates its own assertion samplers. The transitive `$initstate` selection can also
  remove runtime assumptions derived from `$initstate`. This broadens the replay environment.
  `removed_initial_assumptions.txt` and `result.json` list the removed cells.
- A proof engine's pass needs a separate bounded reachability check. This applies to BMC,
  replay, X-propagation, and engine portfolios. The check uses the actual prepared proof model,
  keeps its initial values and assumptions, removes assertions and design covers, and adds
  one cover enabled only at the final checked step. It uses `smtbmc:yices` regardless of the
  proof engine. Thus Yices is required to earn a pass with ABC too. `reachability/` holds the
  separate solver evidence. An unreachable final step or missing reachability evidence gives
  `unknown`, exit 1. A timeout or solver error cannot earn a pass.
- Reachability means at least one path satisfies the assumptions through this bound. It does
  not show that each assertion's enable condition is reachable. It does not establish
  satisfiability after the selected bound.
- VCD has whitespace-separated tokens. Line breaks do not delimit value changes. The parser
  validates the complete header and the body through the selected timestamp. It preserves
  binary X and Z values. It supports nested scopes, equal-width aliases, memory scope
  hoisting, `$dumpvars`, `$dumpall`, and `$dumpon`. It refuses dump gaps (`$dumpoff`), real,
  event and string data, malformed or unsupported commands, conflicting alias widths,
  duplicate variable paths before or after memory hoisting, ranges that disagree with widths,
  backward times, and unknown clocks or multiple edges at one time when counting cycles.
  Timescales must be explicit and have multiplier 1. Other multipliers are refused because
  Yosys replay takes an absolute time with one unit. An ambiguous default scope needs `--scope`.
- FST conversion runs with `rvw.common.proc.run_group`. It first writes a temporary VCD and
  checks the converter exit status. This needs space for the decoded trace, but prevents a
  failed conversion from supplying partial replay evidence. VCD parsing itself reads only
  the required prefix.
- `--out` is validated before taking the directory lock or deleting old evidence. An invalid
  output path leaves existing files intact. Once a valid directory is locked, a new run removes
  the old `result.json`, so a failed run cannot expose an earlier result as its own.

## Validation limits

- Tests use small Verilog designs with real Yosys, SymbiYosys, Yices, ABC, Verilator, Icarus,
  VCD and FST tools. BOOM candidate inventories belong to
  [spinal-boom#4](https://github.com/riscPrint/spinal-boom/issues/4). Unit tests and module
  campaigns do not establish whole-core behavior.
- Regressions keep these review cases:
  - an async-reset design that gave a false pass at depth 8 (all three flows now refuse it);
  - an unwritten register that xprop counted as X-clean (Icarus shows the X after six clocks);
    BMC and replay tests check that undriven or missing state cannot pass by taking only zero;
  - a live RTL or include edit between probes that changed the proven width (each run proves
    its copy; a new run on the edited input fails);
  - two modules with the same RTL basename (only the failing module's check is reported);
  - a macro-built `$readmemh` (refused by the frontend dependency check);
  - ABC's combinational-network error after optimization (exit 2 with a Yices retry command;
    a portfolio keeps another engine's verdict).
- Other tests cover traced and missing registers, contradictory assumptions, assumptions that
  become unsatisfiable at later steps, and positive reachability evidence; integer, packed,
  parameterized, signed and non-ANSI ports, proof defines, replay ties, unreadable port metadata
  and failed probes; async loads, set/clear controls, latches, tied and unused child state,
  fine-grained cells, memory async reset controls and asynchronous memory reads; nested and
  symlink includes and refused dependencies; tool replacement, edit-and-revert and PATH changes
  after capture; Python forwarding wrappers for Yosys and Yices; the `smtbmc:abc` refusal; and
  the BOOM replay script's shell arguments.
- Installed interpreter libraries, shared libraries and tool data remain trusted runtime
  inputs. This capture does not copy or sandbox a complete installed toolchain.

## X campaigns and four-state replay

```sh
rvw formal xprop --verilog design.v --top Top --outputs --replay icarus --out out/x
rvw formal xprop --verilog comb.v --top Comb --outputs --combinational --x-inputs --replay icarus --out out/comb
rvw formal x-sweep --verilog design.v --top Top --module Unit --module Comb --depth 8 --module-timeout 30 --campaign-timeout 300 --out out/sweep
```

`--replay icarus` declares the native Icarus Verilog 4-state backend (`iverilog`, `vvp`).
The run captures these tools before elaboration. It replays each solver input sequence
on the copied source RTL with `SYNTHESIS` defined. It does not load binary solver state
into the DUT. Registers and memories keep their native initial values. The monitor
preserves X and Z bits. A target is `confirmed` only when this replay observes an unknown
bit at that target during a checked step. A conditional target also needs valid to be
exactly 1. The replay log records the target, step and full binary value with X/Z bits.

`inventory` lists every selected target. A solver finding alone is a `candidate`.
A replay failure, missing trace/input, or a replay without X gives `inconclusive`.
`not_reported` means the solver did not report that target. It is not a target proof.
The formal `status` and exit code keep their existing meaning. A replay does not turn
an encoded formal failure into a pass. The `backend` field names Yosys X encoding;
`replay.backend` names Icarus. Source `if`/`case` optimism can differ from pessimistic
encoded mux behavior. A non-reproduced finding remains inconclusive.

Before X encoding, memory mapping expands memories to state cells. The flow records
unencoded cell types. An unencoded data cell prevents a pass. Formal monitors and their
assumptions remain in the design. An unencoded memory cannot earn a clean result.
`--x-inputs` exposes separate free X masks for data inputs. Replay combines each data bit
and its mask without selecting a binary replacement for an unknown. Clock, reset and
ties remain defined. Reset release is checked after `--reset-cycles` and `--settle`.
Uninitialized memories and power-control transitions use the same campaign: leave memory
state uninitialized and power inputs free, or use `--tie` for a restricted environment.
There is no UPF power model or asynchronous power-event model.

`--combinational` makes a clock-free harness with immediate assertions. It refuses
state, including incomplete assignments that infer latches. Sequential runs retain
clock and state-control checks. No synthetic DUT clock is added.

`x-sweep` discovers modules in the selected top's elaborated hierarchy. It runs a separate
output campaign for each module, or each repeated `--module`. It uses Icarus replay and
automatically selects the clock-free harness when the clock port is absent. Inputs at
each module boundary are free. A confirmed module result does not establish reachability
in the enclosing core or a distinct core bug. Each entry records its target inventory,
result path and disposition. Specialized module names that cannot be selected as plain
Verilog tops remain inconclusive. Time limits include child probes, proofs and replays.
The campaign limit starts before discovery; each discovery subprocess also uses `--timeout`.
Unrun modules stay in the inventory. The command returns 1 with status `inconclusive`:
it is an inventory, not an acceptance gate. Use the machine's core lock for large designs.

### Bounded witness collection and parent replay

Use `xprop --first-failure` or `x-sweep --first-failure` to stop each solver
after its first failure trace. Native replay still observes every selected target.
Targets without evidence stay `not_reported`. This option does not turn a timeout
into a pass. Increase the module and campaign budgets when required.

Use `rvw formal x-context` to observe hierarchical signals in the parent RTL.
This native Icarus run starts from reset. It does not inject solver state or free
module inputs. Give `--verilog`, `--top`, repeatable `--signal instance.port`,
`--depth`, `--reset-cycles`, a positive `--timeout`, and `--out`.
Use `--tie PORT=VALUE` for every external input except the clock and reset.
The inputs stay constant. Select values that form a legal environment for the design.

The result records each signal as `reachable-in-core` only if the complete native
run observes X/Z after reset. This label describes an unconditional signal value,
not a valid transaction or an architectural failure. The selected top must be the
real core to make a core-context claim. Check payload validity separately.
A signal with no X/Z observation stays `inconclusive`. This run cannot prove
`unreachable`. Compile errors, timeouts and capture problems stay inconclusive.
The command returns 1 for all results. It never reports a design pass.

## Limit ownership

Multi-clock and asynchronous state: [#46](https://github.com/riscPrint/risc-v-workstation/issues/46). X campaigns: [#67](https://github.com/riscPrint/risc-v-workstation/issues/67). Counterexample debugging: [#60](https://github.com/riscPrint/risc-v-workstation/issues/60). Engine depth: [#21](https://github.com/riscPrint/risc-v-workstation/issues/21). Shared runner: [#117](https://github.com/riscPrint/risc-v-workstation/issues/117).

Retained limit: Only validated engine releases and supported synchronous state qualify. Missing reports, unsupported state, free inputs and replay assumptions retain their documented error or inconclusive outcomes.

## Counterexample what-if replay

Replay a failing `rvw formal bmc` result through native Yosys `sim`:

```sh
rvw formal cex --result out/bmc --out out/replay --json
rvw formal cex --result out/bmc --edit bad@0=0 --out out/whatif --json
```

`--trace-index` selects a witness from `result.json` (default 0). Each repeatable
`--edit PORT@TIME=INTEGER` changes a top-level input at an existing VCD timestamp.
Values use decimal, `0x` or `0b`. An edit lasts until the next change to that input
in the original witness. It does not tie the input for all later cycles. Clock and
reset are inputs too. Editing them changes the replay environment.

The command first replays the original witness. It then replays the edited witness
against the same captured model. It uses `sby/model/design.il`, before SBY clock
conversion. `clk2fflogic` and `chformal -lower` let `sim` evaluate clocked checks.
VCD input is converted to FST before simulation. Each replay writes `wave.vcd`,
`wave.fst`, `summary.json`, the Yosys script and log. Initial state comes from the
original witness where Yosys can map it. Missing state keeps the model's initial
state. The edited replay does not load later witness state over computed state.

`inputs/` retains the original result, witness, model, copied RTL, checks and
wrapper. `input_capture` maps source paths to copied bytes and hashes. The result
keeps the original declared `restrictions`. Assertions and assumptions stay in the
model. An observed assumption violation makes the disposition `inconclusive`.
Use a separate output directory. The command refuses output paths that overlap
the formal run. It does not change that run.

The result uses `rvw.formal.cex/1`. `status` is always `inconclusive`, with exit 1.
`disposition` is `reproduced` only when the original replay observes a property
listed in the formal failure report and the edited replay observes that same
property. `failure_not_observed` means that the original replay observed the
property and the edited replay did not. A tool error, missing baseline failure or
assumption violation gives `inconclusive`. No disposition proves correctness.
Unknown state can hide a failure. Only the selected finite witness is replayed.

For Spinal designs, supply metadata from the same elaboration:

```sh
rvw formal cex --result out/bmc --out out/debug --edit bad@0=0 \
  --hgldd build/spinalwaves/hgldd --pdg build/spinaltrace/pdg.json \
  --criterion line:Top.scala:20 --at-time 9 --open --json
```

HGLDD and PDG inputs are copied. `spinalwaves-check` checks typed lookup on the
edited wave. `--open` launches `surfer-tywaves` only after that check completes.
The result also gives its argument vector. SpinalTrace `dyn-pdg` runs on the
**original replay wave**, where the assertion fails. Select the failing assertion
with `--criterion`. Set `--at-time` to its pre-edge sample time in VCD units.
The wrapper scopes are `rvw_formal_top dut`. The top module is the original design.
Logs and `dynpdg.json` stay in the output directory. A missing tool or failed
lookup reports `inconclusive` in `navigation`. A launched GUI is not a verified
navigation result. Preserve the Scala files at the source paths in the metadata.

MCP exposes the same command as the background tool `formal_cex`. It accepts
`result`, `out`, `trace_index`, `edit` (array), `timeout`, `hgldd`, `pdg`,
`criterion`, `at_time`, and `open`. The timeout bounds each native subprocess.
Cancellation stops each native process group. A GUI explicitly opened by the
user stays open after the replay job ends.

### Validation and limits

The native regression uses `Top` with `assert(!bad)` and `assume(!guard)` at each
rising edge. BMC selects `bad=1` at time 0. Original replay reproduces the failure.
`bad@0=0` removes the observed failure. `guard@0=1` violates the assumption and
stays inconclusive. Tests also cover preserved inputs, refused output overlap,
invalid edits, converter failure and the MCP runner.

Optional viewer tests check command wiring with a test executable. They do not
validate real Surfer or SpinalTrace navigation. A real Spinal elaboration with
matched HGLDD, PDG and Scala source navigation remains to be checked. This first
increment supports BMC results only. It does not minimize input changes, shorten
the failure, remove irrelevant assumptions, or prove that an edited trace is a
legal counterexample. Those parts of issue #60 remain open.

## Proof engines and bounded depth search

Use the source, clock, reset and tie options from `bmc`:

```sh
rvw formal prove --verilog counter.sv --top counter --out out/proof --timeout 60
rvw formal bmc --verilog counter.sv --top counter --engine btor:pono,btor:btormc --out out/bmc
rvw formal depth-search --verilog counter.sv --top counter --depth 4 --max-depth 64 --budget 120 --out out/search --json
rvw formal prove --verilog counter.sv --top counter --cut count:4 --out out/cut
```

`prove` defaults to the parallel portfolio `abc:pdr,aiger:avy`.
BMC supports `btor:pono` and `btor:btormc`. These SBY engines are bounded.
Do not mix engines that require different modes. Each executable is captured.
SBY stops the other engines after its first conclusive answer. Conflicting PASS
and FAIL answers in the log produce an error. An engine stopped before its
answer cannot be cross-checked. Timeout cannot earn a proof.
The assertion, clock, state-control and assumption reachability guards remain.
Results add `proof_kind`: `bounded` or `unbounded`. The reachability guard is
bounded. It does not establish assumption activation for all time.

Depth search doubles the depth up to `--max-depth`. It stops on failure,
unknown, error, timeout or budget exhaustion. Each attempt has its own capture
and result directory. Each attempt checks its current inputs. It does not reuse
proofs between attempts. The total budget starts before the first attempt.
Native cleanup and frontend setup can extend elapsed wall time.
The summary reports the largest bounded pass. It always returns exit 1.
A bounded search cannot earn an unbounded proof.

`--cut SIGNAL:WIDTH` replaces a DUT signal with unconstrained `$anyseq`.
The prepared model supplies its checked width. This is an overapproximation.
No assumption restricts the cut value. A pass applies to all cut values.
An abstract failure reports `unknown` with `abstraction_counterexample`.
It is not a confirmed DUT failure. Interface contracts, dependency checks,
circular-assumption rejection and RAM abstraction contracts remain open.

## SBY campaigns and property history

The runner is separate from full SVA language support:

```sh
rvw formal sby-regress campaign.toml --out out/campaign-1 --timeout 60 --json
rvw formal sby-history out/campaign-1 out/campaign-2
```

Example manifest:

```toml
core = "external"
config = "rtl-v1"

[[property]]
id = "counter_limit"
sby = "counter.sby"
top = "counter"
config = "rtl-v1-reset-one-cycle"
requirements = ["REQ-COUNT-1"]
assumptions = ["reset starts active"]
```

Each job must have one assertion after preparation. Use one SBY task with
`[options]`, `[engines]`, `[script]` and `[files]`. Modes are `bmc` and `prove`.
Engines use plain names without extra options. File targets are unique basenames.
The runner captures manifests, jobs, listed sources and tools before execution.
Declare full dependencies in `[files]`. Transitive closure, property attribution,
assumption activation and vacuity are not checked. Each C3 row records these
limits as `inconclusive`. Raw engine passes are conditional observations.
They cannot establish design acceptance or a non-vacuous proof.

Outputs use C3 `results.json` and C4 `verdict.json`. `formal_status` preserves
`bounded_pass`, `unbounded_engine_pass`, `counterexample`, `timeout`, `unknown`
and `error`. C4 stays inconclusive. The command returns 1.
Keep each fresh campaign directory for history. `sby-history` groups C3 samples
by property id. Each sample retains assumptions, requirements, configuration
and job hash. A matching name cannot establish proof equivalence or reuse.

The native slang plugin loads on this host. However, it rejects
`assert property (@(posedge clk) a |=> a)` with `SVA unsupported`.
Full SVA remains blocked by language support in that plugin.
Do not use `--ignore-assertions` for proof jobs. Sampling regions, multiple
clocks, reset semantics and temporal sequences remain unqualified.
Positive and negative semantic cases on each engine remain required.

Native Avy can crash on a constant-safe AIG. That case returns `error`.
A portfolio can still return a conclusive answer from another engine.
Constant cut bits, repeated aliased bits and clock cuts are refused.

## riscv-formal

`rvw --project /path/to/rvw.toml formal riscv --out /new/output --timeout 60 --json`
runs the exact check list in `[riscv_formal]`. The timeout applies to generation
and to each check. Use the core's machine lock and `nice` for native runs.
The output directory must be new. The runner copies the checker and design
inputs there. It does not modify the core or the riscv-formal checkout.

Required project fields:

| Field | Meaning |
|---|---|
| `root` | Native riscv-formal checkout with `checks/` and `insns/`. |
| `wrapper` | Project-owned SystemVerilog wrapper template. |
| `verilog` | Nonempty list of design source paths. |
| `isa` | `rv32i`, `rv32im`, `rv32ic`, `rv32imc`, or their `rv64` forms. |
| `nret` | Must be 1 in this increment. Wider retirement is refused. |
| `checks` | Exact generated task names. Must include `cover`. |
| `depth` | Bound from 2 to 200 cycles. |
| `solver` | `bitwuzla`, `yices`, `z3` or `boolector`. |
| `defines` | Optional single-line Verilog definitions and assumptions. |
| `ports` | Table from each RVFI field name to its distinct DUT port name. |

The wrapper declares `rvfi_wrapper`, with `clock`, `reset` and
`` `RVFI_OUTPUTS ``. Put `@RVFI_CONNECTIONS@` once in the DUT port list.
The runner replaces it with the project port map. The wrapper must supply the
memory environment, clock/reset connections and input constraints. Review these
constraints before using a result. The runner does not certify that they model
the intended system. It does not check the DUT's port widths before synthesis.

Supported check names are `insn_<instruction>_ch0`, `reg_ch0`, `pc_fwd_ch0`,
`pc_bwd_ch0`, `causal_ch0`, `unique_ch0` and `cover`. A task that the
selected ISA does not generate produces an inconclusive error. No task is
silently skipped. CSR, vector, atomic, floating-point and multi-channel checks
are not supported by this interface.

`results.json` uses C3. Missing status, tool errors, cover failure and timeouts
are inconclusive. Assertion FAIL is a failure. PASS needs both an SBY PASS
status and exit 0. Without retirement cover, assertion PASS records remain
inconclusive. A reached retirement does not show that each instruction was
reached. All properties remain bounded. `verdict.json` uses C4: failures reject;
other results stay inconclusive. Even a complete bounded run cannot earn gate
acceptance. Adapter conformance and committed gate identity remain work for #63.
C1 simulation results are not fabricated for formal jobs.

## Examples and provenance

[BOOM](../../../../examples/boom/formal/rvw.toml) and
[VexRiscv](../../../../examples/vexriscv/formal/rvw.toml) supply separate settings.
BOOM selects ADD, SUB and retirement cover at depth 20. VexRiscv selects
all 37 upstream RV32I instruction checks and reg at depth 20. It selects
pc_fwd, pc_bwd, liveness, unique and causal at depth 30. It uses BTORMC for
pc_fwd, ABC bmc3 for the other assertions, and Bitwuzla for retirement cover. Liveness alone enables the
upstream VEXRISCV_FAIRNESS assumptions. These restrict bus stalls and traps.
These assumptions are part of the result, not a claim about a real bus. Set `RISCV_FORMAL` to a native checkout.
BOOM also needs `SPINAL_BOOM/formal/BoomFormalTop.v`. Generate that RTL in the
owner-approved private clone. The runner never elaborates in the source checkout.

The BOOM wrapper and settings are adapted from `riscPrint/spinal-boom`, commit
`19c6244bca7c9442b34f6b536a63e2013ec36cf4`, `formal/wrapper.sv` and
`formal/checks.cfg`. The core source stays read-only. The VexRiscv wrapper is
adapted from `YosysHQ/riscv-formal`, commit
`c992aa61fdfe0846c5ed90324c596202a1c69b76`, `cores/VexRiscv/wrapper.sv`.
Its project selects the `FormalSimple` RTL snapshot in that checkout. This is
not the workstation RV32IM simulation variant. The run records hashes of the
actual copied RTL, wrapper and checker inputs. No third-party RTL is vendored.

## Decisions and limits

Reuse upstream `genchecks.py` and SBY. Keep all core signal names and memory
constraints in project data. Require cover to expose shallow reset-only results.
Do not claim full ISA proof, adapter conformance, privileged-mode correctness,
or correct memory transactions from this bounded run. Independent transaction
checks for retire width, order, traps, killed instructions, memory lanes and
multiple effects remain open. The current tests cover configuration refusal,
private input copies, missing status, failing cover, timeout and result mapping.

## Sail SystemVerilog checks (#64)

`python -m rvw.formal.sail_subset` compiles an explicit arithmetic slice
through the native Sail 0.20.1 SystemVerilog backend. It extracts the exact
ADD, SUB and ADDI right-hand expressions from the pinned rule file below.
The adapter supplies `bits(32)` operands and Sail sign extension for ADDI.
It binds the older `sub_vec` name to the compiler primitive `sub_bits`.
It specializes integer widths, keeps the pure generated modules and removes
the unused simulator top and runtime types. It does not rewrite generated
arithmetic logic. It retains the raw backend output beside the RVFI models.
Upstream riscv-formal supplies instruction decode, x0 write suppression,
PC advance and RVFI wiring. This is not the full Sail machine or an independent
decode implementation. Memory, CSR, traps and privilege are outside the slice.

Install the native compiler with `opam install sail.0.20.1 --jobs=2` in an
appropriate opam switch. This is separate from the simulator installer.
The opam source archive is `sail-0.20.1.tbz` from the Sail 0.20.1 release.
Its SHA-256 is
`ba81b8d7aa5705e04064013ab20c006b80c6db44f95225ac4fbf6042297e50eb`.
The installer does not install this compiler. It still installs the separate
ISA simulator when requested.
The generator requires compiler version 0.20.1 and the exact rule hash.
It records compiler bytes, version, source and generated hashes, options,
XLEN, compiler library hashes and the subset boundary in `manifest.json` under the output directory.
Generated files and measured proof results stay outside the repository.

```sh
python -m rvw.formal.sail_subset --model /path/to/sail-riscv \
  --compiler /path/to/opam/bin/sail --riscv-formal "$RISCV_FORMAL" \
  --out /tmp/sail-subset
```

Select the generated files in a copy of the core project settings:

```toml
[riscv_formal.instruction_models]
add = "/tmp/sail-subset/insn_add.v"
sub = "/tmp/sail-subset/insn_sub.v"
addi = "/tmp/sail-subset/insn_addi.v"
```

Run the same checks without overrides to use the independent upstream
arithmetic models. Run `test_riscv_formal.py` with `SAIL_MODELS` set to the
generated directory for independent correct and intentionally wrong arithmetic
fixtures. The fixture equations are handwritten. The generated model never
uses DUT results as its oracle. These tests do not establish adapter conformance.

The first intended subset is RV32I ADD, SUB and ADDI, with one retirement
channel and no memory, CSR, trap or privileged effects. The source baseline is
[sail-riscv 0.15](https://github.com/riscv/sail-riscv/tree/549e723031b34b5ffea5bbb56367be15c7a38a9e),
commit `549e723031b34b5ffea5bbb56367be15c7a38a9e`.
`model/extensions/I/base_insts.sail` has SHA-256
`07ce0b099023b6e9ce9aeedb0be15a800f2cec8dd7382a076853391537b5add3`.
The rule locations at that commit are:

| Instruction | Decode rule | Execution rule |
|---|---|---|
| ADD | `encdec RTYPE`, line 225 | `execute RTYPE`, lines 237 to 251; ADD at 239 |
| SUB | `encdec RTYPE`, line 233 | `execute RTYPE`, lines 237 to 251; SUB at 247 |
| ADDI | `encdec_iop` and `encdec ITYPE`, lines 145 to 155 | `execute ITYPE`, lines 158 to 169; ADDI at 161 |

The compiler is a separate prerequisite. `sail_riscv_sim` from the binary
release is an executable ISA simulator. It is not the Sail compiler and does
not expose the SystemVerilog backend. The Sail compiler's backend option is
`--sv`; see the [Sail manual](https://github.com/rems-project/sail/blob/master/doc/asciidoc/usage.adoc).
A simulator version alone cannot identify the compiler or its backend.

Full-machine Sail generation, independent decode and state-transition
properties remain open. The expression slice cannot establish those claims.

## Sampled event BMC

Use `bmc --event-model` for sampled events on `--clock`. Add each extra top input
with `--event-clock PORT`. This option also enables the event model. Add
`--async-reset` separately to allow `$adff` and `$adffe` constant-value reset cells.
These controls remain refused without both options. MCP `formal_bmc` accepts
`event_model`, `event_clock` and `async_reset`.

SBY runs with `multiclock on` and applies Yosys `clk2fflogic`. One solver step
is one global input sample. Each declared clock can change independently.
No rate, phase, fairness or clock relationship is assumed. Simultaneous edges
and clocks that stop are included. This model covers arbitrary sampled clock
rates. It does not model analog metastability, propagation delay, or pulses
that rise and fall entirely between two samples.

An asynchronous reset acts at a sample even when no clock rises. Free reset
inputs can make inter-edge pulses. The optional reset harness still counts
`--reset-cycles` rising edges of the primary clock. It then holds reset inactive,
unless `--free-reset` allows later pulses. Other reset inputs remain free unless
tied. This sequence does not ensure that every other domain sees a clock edge
during reset. State without RTL initialization remains free.

The result records `event_model`, declared clocks, relationships, async-reset
support and the solver-step meaning. Failure `step` is a global sample index.
Failure `cycle` is null because no common cycle number exists.
A bounded pass applies only to this sampled model and depth.

Undeclared, derived, gated, constant and falling-edge clocks remain refused.
Clock ports cannot be tied or used as the harness reset. Async loads, set/clear
cells, latches, fine-grained state and memory async reset controls remain refused.
The pre-optimization probes also check unused and tied state.
`from-sim`, X flows and native replay retain the original one-clock restrictions.
Related clocks with declared ratios or phase constraints are not yet supported.

Small pass/fail designs and refusal cases are in
[SpinalChecks/examples/events](../../../../SpinalChecks/examples/events).
Tests check the independent-clock false-pass case and a pulse that clears an
async-reset register without clearing a synchronous-reset register.

Formal generated assertions sample on clock edges even when the state has an async
reset. Reset still gates the check. Formal mode omits monitor text reports.
Raw assertions with an async reset in their sensitivity list remain refused.
Their trigger semantics are outside this increment.

## Sequential equivalence (first increment, issue #18)

```sh
# Export RTL from each revision before this command. Keep the files separate.
rvw formal equiv --gold old/Top.v --gate new/Top.v --top Top \
  --clock clk --reset reset --reset-cycles 2 --timeout 60 --out out/equiv --json
# Rename a flattened state signal explicitly. This is a mapping, not an assumption.
rvw formal equiv --gold old/Top.v --gate new/Top.v --top Top \
  --pair stage.old=stage.new --settle 2 --dsec --out out/equiv
```

The first design is a four-bit synchronous pipeline. Tests cover an equal arithmetic
refactor, an equal retiming, renamed state, and a changed arithmetic result.
The output contract is `rvw.formal.equiv/1`. Exit 0 means `equivalent` (proved).
Exit 1 means `not_equivalent` with a VCD counterexample, or `inconclusive`.
An invalid or busy output directory exits 2. Each run owns its output directory
until it writes the result. A new run removes the old result first.

Each side uses the existing captured RTL frontend and tool bindings. Both designs
must have the same ordered port interface. One rising-edge clock is supported.
Async controls, latches, memories, blackboxes, design properties and explicit
nondeterministic cells are refused. State names must cover every register bit.
The command pairs register names of equal width automatically. Repeat `--pair`
for renamed state. An unmatched register always prevents an equivalence result.
The mapping is an inventory. The solver does not assume that paired values agree.

Eqy creates partitions. The command matches boundary ports and keeps internal
state inside each output cone. Independent output cones can form separate
partitions. All must pass. Internal state cutpoints are refused.
SymbiYosys proves each partition with `yosys-abc`, using `scorr; pdr`.
The flow uses two-state values, independent initial state on each side, and no
user assumptions. An unknown or absent partition, a missing witness, a solver
error, or a timeout cannot produce `equivalent`. A failure describes this initial
state model. It need not be a reachable hardware difference after a real reset.

`--reset` drives the same synchronous reset sequence into each design. It is active
for `--reset-cycles` clocks, then inactive. Output checks start after that sequence
and `--settle` extra clocks. Without `--reset`, checks start at time zero, unless
`--settle` is set. These unchecked startup clocks are an explicit restriction.
Only `--latency 0` is supported. There is no output cycle shift or protocol adapter.
No reset port means no reset sequence is inferred. Inputs other than clock and
reset remain free. Results list the reset, settle and latency settings.

`--dsec` also exports each wrapped design to AIG and runs native ABC `dsec`.
Its log is advisory. ABC's initialization and name matching differ from the eqy
obligations. A dsec message cannot replace the partition proof. A dsec timeout
still makes the command inconclusive. Native dsec as an authoritative backend,
state encoding maps, nonzero output latency, blackbox contracts, multiple clocks,
and a scalable partition dependency proof remain part of the epic.

The command takes exported RTL files. It does not check out a source repository,
run an elaborator, or claim that a supplied revision label produced those files.
For tracked RTL, use `git show REV:path/to/Top.v > old/Top.v` for each side.
For Spinal designs, elaborate each committed revision in a separate build area.
Do not build or change an owner's shared core checkout.

### Validation scope and export gap

The committed equivalence tests use small Verilog designs. Run them from the
workstation root with the native formal tools on `PATH`:

```sh
nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/formal/test_equiv.py -q
```

This increment has no committed BOOM leaf export recipe. It does not establish
BOOM leaf or whole-core equivalence. A source revision label alone does not
establish the origin of generated RTL.

A reproducible source-revision comparison still needs a tested export flow.
It must declare the generator dependencies and settings for each revision.
Module selection must use the project's generated Verilog and project data.
Core names and settings must stay outside `rvw/src`. Copying a Scala class and
selected helpers into a temporary harness is not a supported export flow.

## Imported SVA through slang

`rvw formal bmc --frontend slang` selects the pinned native plugin in `RVW_SLANG`.
Install it with `scripts/install.sh --with-formal`. Source the generated `env.sh`.
The default frontend stays `verilog`. The SBY campaign runner stays independent.

```sh
rvw formal bmc --frontend slang --verilog design.sv --top top \
  --clock clk --engine smtbmc:yices --depth 12 --out proof
```

The qualified subset has inline `assert property` and `assume property`, each with
an explicit `@(posedge clk)` on the selected clock. The property can contain a
Boolean expression, optional `disable iff (condition)`, and single-argument
`$past`, `$rose`, `$fell`, `$stable` and `$changed`. Normal bit and arithmetic
expressions are allowed. User function calls in properties are refused.
`$past` uses one prior sample. Guard its first use with initialized valid state.
`$rose` and `$fell` check the least significant bit. `$stable` and `$changed`
compare the whole value. Prior samples before the first edge remain unconstrained.

The model uses two-state, pre-update samples at one rising edge per formal step.
Nonblocking state updates affect the next sample. Inputs have one value per step.
`disable iff` suppresses the current check when its condition is true. This subset
has no pending temporal threads to abort. It does not model simulator delta cycles,
four-state X/Z transitions, or reset events between edges. Existing reset handling
and the separate bounded reachability check still apply. A pass is bounded by depth.

Qualified engines are `smtbmc:yices` and `abc:bmc3`. Other engines, event BMC,
macros/includes, named properties, sequences, clocking blocks, action blocks,
cover/restrict, temporal implication, delay, repetition and multi-argument sampled
functions are refused before SBY starts. There is no full temporal SVA claim.
The native frontend checks syntax and types. The input guard checks the supported
subset even in unused text. A frontend failure cannot produce a passing result.

The command captures the plugin bytes and checks its source identity before result
publication. The frontend reports RTL dependencies. Reads outside the copied input
set are refused. Later proof stages read the sealed RTLIL model. `result.json`
records `frontend: "slang"` and the existing input capture records.

## Capacity templates and contracts

`rvw formal template KIND --entries 4 --width 3 --out monitor.sv` writes a
SystemVerilog monitor. Instantiate it next to the DUT. The monitor adds assertions.
It adds no assumptions. `entries` and `width` come from the reference specification.

| Kind | Interface and property |
|---|---|
| `rob`, `credit` | `count`, accepted `push` and `pop`: capacity, legal events and exact count conservation. Simultaneous events have zero net change. |
| `freelist` | `free_bits`, `allocated`: the bit sets do not overlap. |
| `rename` | `valid`, packed `tags`: valid entries have distinct physical tags. Use for allocation lanes or a map that requires injectivity. Aliases in a move-elimination map need another specification. |
| `issue` | `issued`, `valid`, `ready`: at most one grant; each grant has a valid, ready entry. |
| `lsq` | `load_fire`, `older_store`, `address_match`, `forwarded`, `load_data`, `store_data`: a load that matches the selected older store forwards its data. The harness must select the youngest matching older store. |

These are local safety templates. They do not specify a complete ROB or LSQ.
They do not prove retirement order, flush recovery, fairness or eventual progress.
The native tests give each monitor a small reference design and a separate seeded fault.

`rvw formal contracts plan.json --budget 60 --engine abc:pdr --out proof`
runs fresh unbounded jobs. A plan declares shared unsigned signals, predicates
and component ports. All components have one `clk` and one active-high `reset`.
The runner checks exact port widths and directions against the elaborated RTL.
It connects ports with the same signal name in the closed composition.

```json
{
  "verilog": ["units.sv"],
  "signals": {"token": 1, "accepted": 1},
  "predicates": {"token_ok": "token == 1", "accept_ok": "accepted == 1"},
  "components": [
    {"id": "producer", "top": "Producer", "inputs": [], "outputs": ["token"],
     "assumes": [], "guarantees": ["token_ok"]},
    {"id": "consumer", "top": "Consumer", "inputs": ["token"], "outputs": ["accepted"],
     "assumes": ["token_ok"], "guarantees": ["accept_ok"]}
  ]
}
```

Each assumption names the exact predicate that a neighbour guarantees.
An assumption can use only the consumer's inputs. Missing providers, multiple
drivers and circular dependencies are errors. Each local proof assumes only its
listed predicates. The closed proof removes all generated assumptions and checks
all guarantees together. This last check is mandatory. It also checks the actual
wiring. A local proof alone cannot earn composed success.

Exit 0 means `conditional_proved`. Every component and the closed composition
must have an unbounded pass with the existing bounded reachability guard.
Source RTL assumptions remain environment restrictions. Each obligation records
the assumption cells and their source locations. This flow does not prove
that every assertion activation is reachable. It does not certify a supplied RTL
export's generator revision. The budget limits each solver to the remaining time
and stops new jobs after expiry. Frontend probes can add time beyond this budget.
Use an outer process deadline when a strict total wall time is required.
Fresh output directories are required. No cached proof is reused.

## Explicit abstraction

BMC and prove accept `--abstraction plan.json`. The file contains only `cuts`:

```json
{"cuts": [{"signal": "ram_read_data", "width": 32, "kind": "memory-read"}]}
```

Kinds are `cut`, `blackbox-output`, `data` and `memory-read`. Each cut replaces the
selected signal with an unconstrained value at each step. Width checks and clock
cut guards remain active. For a black box, list each output. This does not remove
the instance or bypass clock and state checks. For a memory, cut each read-data
signal. This loses address, collision, initialization and inter-port correlation.
It keeps all concrete read values possible. Undefined read-under-write behavior
stays free. This is an overapproximation, not a typed RAM refinement proof.
Data abstraction frees the declared bits; it does not reduce an arithmetic width.

Abstraction plans cannot add assumptions. Use a checked interface contract when
an output restriction is needed. An abstract counterexample is `unknown`, not a
concrete bug. An abstract proof applies to the larger unconstrained behavior set.
The result records each cut, its semantics, kind and captured plan hash.

## Invariant mining and strengthening

`rvw formal strengthen plan.json --budget 60 --out proof` accepts a single
component contract without generated assumptions. Add `samples`, an array of
observed unsigned output values, for example `[{"token": 1}]`.
The command mines minimum and maximum bounds for each output. It proves each
candidate with a fresh unbounded job. An observed bound is never an assumption.
A failed or incomplete candidate is excluded from the final strengthening set.
The final job asserts the target guarantees and the certified bounds together.
Use `smtbmc:yices` for k-induction or `abc:pdr` for IC3/PDR. This supplies joint
assertions to the existing engine. It does not modify an engine's lemma database.
Original RTL assertions remain checked in every job.

Limits: unsigned interval mining only; no relational, memory or predicate mining.
There is no measured capacity gain or commercial parity claim. A final pass is
unbounded under the source RTL assumptions and the declared reset protocol.

### BOOM free-list export recipe

`SpinalChecks/boom/freelist-capacity.py` prepares the `RenameFreeList` module from
an existing BOOM Verilog export. It leaves core sources unchanged. Run:

```sh
rvw/.venv/bin/python SpinalChecks/boom/freelist-capacity.py \
  --verilog /path/to/BoomSimTop.v --out /tmp/freelist-plan
scripts/with-lock.sh boom nice -n 10 rvw/.venv/bin/rvw formal contracts \
  /tmp/freelist-plan/plan.json --engine abc:pdr --depth 8 --budget 60 \
  --out /tmp/freelist-proof
```

The named properties check allocation payload range and membership in the debug
free set. Inputs stay free. The recipe disables native assertions in the copied
module because their environment protocol needs a separate harness. It records
the input export hash. It does not certify the export's source revision. These
local properties do not establish free-list protocol correctness or whole-core safety.
