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


## Custom compiler and reference exports

`rvw formal custom-isa CUSTOM.json --out OUT --backend-sources BASES` generates
GCC and LLVM patches plus a Spike extension for pure version-1 instructions.
MCP `formal_custom_isa` accepts the same optional `backend_sources` directory.
Version-2 state/memory/trap effects are not mapped to these software backends.

`BASES/sources.json` uses `rvw.custom-backend-bases/1`. Each logical compiler file
has its full revision and SHA-256. Source files occupy those paths under BASES.
See `examples/custom-isa/compiler-bases.json` for pinned GCC 15.2 and LLVM 21.1
inputs. The checked-in example patches are generated from these exact bytes.
With no base directory, output contains fragments only and reports the missing
parent integration as a gap.

GCC output adds instruction patterns and `__builtin_riscv_rvw_NAME` entries.
LLVM output adds instruction records, `llvm.riscv.rvw.NAME` IR intrinsics and
selection patterns. Patches target a project compiler with the custom extension
enabled. No runtime feature discovery is added. Clang C builtin declarations
are not generated. Applying a patch does not establish a compiler build pass.

`OUT/backends/spike.cc` implements the pure word expressions and registers
instruction/disassembly handlers. Run `OUT/backends/build-spike.sh` with the
same `SPIKE_PREFIX` used for the co-simulation shim. It writes `libcustom.so`.
Merge `platform.fragment.json` into project data with the correct library path.
The existing co-simulation loader captures and loads that declared library.
Native smoke tests compile and execute RV32I/RV64I GNU calling-convention
programs through captured Spike inputs. Without the extension, each program's
custom instruction traps. These are software/reference fixtures, not DUT proof.

Supported exports cover pure RV32I/RV64I R-type data. E handlers, stateful
backend semantics and complete compiler qualification remain outside this
increment. Upstream GCC is GPL-3.0-or-later. LLVM is Apache-2.0 WITH LLVM-exception.
The generated artifact license is not specified. The installed Spike dependency
license is not verified. No generated artifact is installed automatically.

## Custom instruction state, memory and traps

Use `rvw formal custom-effects effects.json --out OUT`. MCP tool
`formal_custom_effects` uses the same generator. See
`examples/custom-isa/effects.json` for complete store, accumulator and trap data.
The format is `rvw.custom-isa/2`. The pure version-1 command remains supported.

Declare all result, normal PC, extra-state, memory and trap effects. Word trees
can read `rs1`, `rs2`, `pc`, `state.NAME` and load response `mem_rdata`. Operations
are add/sub/xor/and/or/sll/srl. Values wrap to XLEN. Trap predicates support
eq/ne/ult/slt/all/any/not. All extra-state updates read pre-state. A trap applies
its own updates and target PC. It suppresses the normal destination/state commit.
x0 suppresses only the integer destination write.

The model supports one completed instruction transition and one load or store.
A memory fault requires an attempted access. The RTL asserts this input contract.
A store attempt and its architectural commit are separate outputs. Project bus
logic must supply correct response data and fault timing. The kernel does not
model handshakes, multiple accesses, AMOs, partial fault side effects or a DUT.

Output contains one SystemVerilog kernel per instruction, `interface.json`,
`plan.json` and `result.json`. The plan has boundary, alias and fault cases.
Generated expected values share the declared semantics. Project reference
vectors and effect mutants must be independent. Their results and gaps remain
explicit. State setup, actual-core binding, software/backend support and full
instruction proof remain separate work.

## Profile clauses and source catalogs

`rvw formal profiles PLAN.json --out OUT` imports named RVA23/RVB23 extensions,
mandatory base/endian/ECALL clauses, nested Sha constituents and the RVB23
hypervisor pointer-mask condition. Attached NOTE paragraphs remain in each
captured obligation. Supervisor profiles inherit user requirements. Optional Sha
activates its pinned constituent requirements. Selecting Sha without a pinned
constituent definition is refused.

Base and standalone clauses are implemented only when `declarations` maps their
stable obligation ID to Boolean true. An ISA string alone does not establish
endianness, ECALL behavior or PMM settings. Implementation declarations remain
separate from mapped, hash-bound proof evidence. Canonical ISA strings can
include H, such as `rv64ih`.

The command writes `index.json` and `catalogs/<source-sha256>.json`. Catalogs use
`rvw.spec-obligations/1`. Each clause retains its source text and explicit checker
and test mappings. `unmapped_checkers` lists missing mappings. Empty mappings
must be reviewed before these files can be adopted by specification diff tools.
The index stores source spans and hashes without copying specification prose.

`examples/profiles/source-index.json` records 273 imported and inherited
obligations from the pinned source revision. `profile_clauses.materialize`
checks source hashes and exact spans before reconstructing catalogs. This data
is a source inventory. It does not establish execution, parameter conformance,
recommendation coverage, complete checker mappings or full profile compliance.
ISA, debug and platform catalogs beyond these profile sources remain open.

## Internal forbidden paths

Use `rvw formal internal-path SECRET PUBLIC --verilog dut.sv --top Unit --out OUT`.
MCP tool `formal_internal_path` runs the same check. Endpoints can name internal
hierarchical wires. Source files must be self-contained SystemVerilog files.

The tool captures the RTL, flattens it and maps memories. It does not cut any
driver. It walks a conservative bit dependency graph. Every cell input can
influence every cell output. This includes clock, reset and control inputs.
`no_path` establishes graph absence for the captured RTL. `path_found` provides
a witness, but does not establish Boolean influence. Black boxes, missing port
directions and node limits prevent an absence result. A path can be spurious
because the graph does not solve Boolean conditions. This is a structural check,
not a two-copy noninterference proof or a design acceptance verdict.

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
  Optional exact proof reuse is described below.
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

The BOOM inventory has a [complete per-target table in PR #235](https://github.com/riscPrint/risc-v-workstation/pull/235).
Keep its [group dispositions on spinal-boom#4](https://github.com/riscPrint/spinal-boom/issues/4#issuecomment-6626689541)
with the parent-context observations. FpPipeline module observations retain
inconclusive whole-core reachability. ITLB inactive payload X values do not
establish invalid transactions. Arbiter results are bounded module checks.
Candidate counts do not count distinct core bugs. New campaigns must retain
unreported targets and update the core issue with their bounds and dispositions.

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

### Native generated-monitor qualification

`rvw/tests/formal/test_generated_sby.py` runs SBY in `prove` mode on small
independent fixtures for 16 generated monitor kinds. Every good fixture must
return `PASS`. Every seeded fault must return `FAIL`. An elaboration error is
not a detected fault. `test_property_library.py` also runs bounded good/bad
checks for the six property intents. These tests use Yices and are slow tests.
`test_csr_spike.py` builds the generated VexRiscv project CSR programs and runs
them on M-only Spike. This tests the software reference, not VexRiscv RTL.
Missing native tools cause a skip. No skipped test supplies verification evidence.

### Typed multichannel bus safety

`formal buses` also generates AXI4 and AXI4-Lite five-channel stall monitors.
It supports qualified TileLink bus types, including B/C/E channels when present.
Each payload includes every recorded sideband. AXI4 checks burst encodings,
FIXED length limits and WRAP length/alignment. AXI-Lite rejects EXOKAY responses.
TileLink starts with opcode checks. Complete fields add transaction checks.
Pre-acceptance offers can change. Hierarchical instances use local
clock/reset ports. Missing fields and unresolved controls stay unsupported.
Complete AXI fields also enable independent transaction trackers. These rows
report `coverage=transaction_safety`. The trackers check per-ID read bursts,
RLAST, write address/data order, WLAST, response IDs and EXOKAY lock flags.
W data can arrive before AW. Reads can interleave across IDs. WSTRB checks
use the paired AW geometry for FIXED, INCR and WRAP bursts, including unaligned
first beats. They also check 4 KiB boundaries and exclusive request options.
`--depth 4` limits pending descriptors and `--max-beats 256` limits write
strobe history. Capacity assertions describe instrumentation limits, not AXI
protocol violations. The MCP tool exposes both controls. Generation does not
run a solver. Memory data and exclusive reservation state remain project
obligations. Full coherent state and negotiated endpoint capabilities remain open.

## Resource safety templates

`rvw formal template allocation_pool --entries 4 --width 3 --out pool.sv`
generates an independent ownership bitmap. The two allocation and two release
lanes carry accepted resource tags. The checker detects duplicate lanes,
out-of-range tags, allocation of live entries, release of free entries and a
DUT live bitmap that differs from independent expected ownership. Release then
allocation permits reuse on the same edge. Override the `INITIAL_LIVE` module
parameter with project reset ownership. Do not connect it to DUT live state.
This is a resource-pool rule, not a complete ROB or rename recovery model.

`cam_match` checks at most one match on active samples. `require_match` also
requires a hit. `counter_bounds` checks the unsigned inclusive range zero to
`entries`. Both use explicit active signals. These templates are available
through `formal_template` MCP. Existing FIFO data ordering, arbiter and stream
rules remain in `QueueChecks`, `StateChecks` and the property library.
Projects must bind their own structures and independent accepted events.
No database inference, fairness, full ROB recovery or real-core proof is claimed.

## UPF isolation import

`rvw formal upf --source intent.upf --bindings bindings.json --out generated`
imports a literal UPF 2.1 domain/isolation subset and generates sampled isolation
checks. MCP: `formal_upf`. See `SpinalChecks/upf/README.md` for exact commands,
binding fields, event semantics and unsupported constructs. Literal retention, supply tables and power-switch gating are also supported.
See the UPF README for their explicit binding maps. Clock-gate Tcl import and
general Tcl remain unsupported. No verification
runs during generation.
## Simple bus protocol generation

`rvw formal template axis|apb|ahb_lite --width N --out monitor.sv` writes a
sampled assertion module. Use one kind at a time. `axis` requires a packed
payload with all enabled AXI4-Stream data and sideband fields. It checks valid
and payload stability under backpressure. It makes no packet-length claim.
`apb` checks setup, access, stable request, wait states and back-to-back setup.
Pack address, write direction, write data and enabled request sidebands into
`request`. Response data and errors are not an independent memory scoreboard.
`ahb_lite` checks active address/control stability during waits and the two-cycle
ERROR response. ERROR permits cancellation of the next address. Pack address,
write direction, size, burst, protection and lock into `request`. This monitor
does not check burst progression, data-phase writes, exclusive memory effects,
or a multi-master AHB bus. All monitors require reset and a rising sample clock.
The standalone monitors use immediate SystemVerilog assertions for simulation
and formal engines. They do not run either engine during generation.

`rvw formal buses --db design.db --out generated` discovers recorded `Apb3`,
`AhbLite3` and `Axi4Stream` bundle types. MCP: `formal_buses`. It derives ports
and packed payloads from typed signal paths. It writes `monitors.sv`,
`binds.sv`, and `result.json`. Load both SV files with the DUT in a frontend
that supports instance `bind`. Top and nested component buses with one recorded
rising clock, reset, and no clock enable or soft reset are supported. APB
requires one select bit. Missing fields, missing clock associations and other
unsupported cases stay named in the report. No bindings gives `no_checks`
and exit 3. Generation is not evidence of compilation or verification.

These additions do not complete #66. Full TileLink cache-state coherence, full AHB
burst/data checks and complete protocol compliance remain open. Native seeded simple-bus tests check monitor behavior;
they do not establish real-device correctness or database-to-RTL integration.

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
| `nret` | Retirement channels, 1..16. Check channel indices must be below NRET. |
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
Each `files.INSTRUCTION.property_trace` entry names a stable property ID,
the pinned Sail path, rule, line, exact expression and execution context.
It records operand bindings and the generated result port. It lists the
upstream shell separately. Do not attribute decode or architectural transition
proofs to this Sail slice. `implementation_options` declares the supported
XLEN 32, NRET 1, uncompressed ADD/SUB/ADDI configuration. The Python generator
refuses other XLEN or NRET values before it creates output. Compiler backend
options and all generated hashes remain in each instruction entry.
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
Related clocks can use the periodic sampled schedules specified below.

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
Async controls, latches, memories, unmodeled blackboxes, design properties and explicit
nondeterministic cells are refused. State names must cover every register bit.
The command pairs register names of equal width automatically.
It then pairs unmatched registers with a unique leaf name and equal width.
Ambiguous names remain unmatched. Manual pairs have priority. Repeat `--pair`
for renamed state. By default, an unmatched register prevents an equivalence result.
`--unmatched-state prove` retains the inventory but lets the solver check every
internal state bit without name pairing. It adds no state equality assumptions.
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
`--latency N` means the candidate output lags the reference by N clocks (0..64).
The reference wrapper delays every output by N clocks. Both wrappers suppress
output checks through reset, settle and these N extra startup clocks. The output
shift applies to all outputs, including status ports. There is no handshake adapter.
Use it only when this fixed-cycle interface contract is intended.
No reset port means no reset sequence is inferred. Inputs other than clock and
reset remain free. Results list the reset, settle and latency settings.

`--dsec` also exports each wrapped design to AIG and runs native ABC `dsec`.
Its log is advisory. ABC's initialization and name matching differ from the eqy
obligations. A dsec message cannot replace the partition proof. A dsec timeout
still makes the command inconclusive. Native dsec as an authoritative backend,
state encoding maps, blackbox contracts, multiple clocks,
and a scalable partition dependency proof remain part of the epic.

The command accepts exported RTL files with `--gold` and `--gate`.
It can also build both source revisions through project data:

```sh
rvw --project examples/boom/rvw.toml formal equiv \
  --gold-rev a1c9b87ada7b2472a025cfd3e8c39a3dd717b27c \
  --gate-rev 0cb0b694413c6eba5837560536cde80dad62ca00 \
  --config small --top ForwardingAgeLogic --settle 1 --timeout 1200 --out /tmp/leaf-proof
```

Set `RVW_HOME`, `SPINAL_BOOM`, JDK 21 and the native tool path first.
Declare `formal.export_dependencies` as the generator repository paths.
Each must be clean and committed. `query.build` owns the elaboration command
and declared sbt dependencies. Export uses an archived source revision and a new
build directory. It does not copy Scala classes into a custom harness or reuse a
cached dependency classpath. Yosys selects the requested module and its children
from project-generated RTL. Missing modules fail closed.

Each export retains `export.json`, source files, generated RTL, selected RTL and
build logs. The proof result records source commits, generator commits, settings
and hashes. Use a new output directory for each revision comparison.
See C6 in `docs/PLATFORM_CONTRACTS.md` for export limits. A leaf proof makes no
whole-core claim. Issue #18 remains an epic.

## Imported SVA through slang

`rvw formal sva-inspect` runs the native Slang parser without synthesis or
property lowering. Use it to inspect typed syntax before selecting a supported
lowering route:

```sh
rvw formal sva-inspect --verilog dut.sv checks.sv --top dut --plugin /path/to/slang.so --out inspect
```

`RVW_SLANG` supplies the plugin path when `--plugin` is absent. MCP
`formal_sva_inspect` has the same inputs. The result lists native node kinds,
operators and assertion nodes. `ast.json` retains the typed native tree.
The compiler capture records Yosys and plugin hashes. Literal includes are
captured with the source files. Native AST addresses are valid only for that
process. They are not persistent property identifiers.

Parsing does not establish lowering or proof support. Both stages remain
`not_run`. `parsed` requires a native dependency report that matches the captured
source closure. A plugin that accepts `--all-deps` but does not write that report
produces `inconclusive`, even when it emits a valid AST. Native compilation
errors and unsealed source dependencies produce `error`. A tree with no active
assertions produces `no_checks`. Runtime libraries are not sealed.

Native parser tests cover unbounded sequence operators, local variables,
liveness, property arguments, default clocking, multiple clocks, checkers and
bind files. These tests qualify parsing only. The lowering support table below
keeps its separate test basis.

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
cover/restrict, nonoverlapped or nested implication, delay, repetition and multi-argument sampled
functions are refused before SBY starts. There is no full temporal SVA claim.
The native frontend checks syntax and types. The input guard checks the supported
subset even in unused text. A frontend failure cannot produce a passing result.

The command captures the plugin bytes and checks its source identity before result
publication. The frontend reports RTL dependencies. Reads outside the copied input
set are refused. Later proof stages read the sealed RTLIL model. `result.json`
records `frontend: "slang"` and the existing input capture records.

### Input commit records

The C3 `source.formal_inputs` object includes `settings_sha256` and
`committed_inputs`. The settings hash covers the full selected configuration,
including port mapping, check options, assumptions and instruction overrides.
The input list covers the copied wrapper template, RTL, checker files and active
instruction overrides. Each row records its copied SHA-256. The runner compares
those bytes with the file at its repository's captured HEAD commit. A row is
`committed`, `modified`, `untracked_or_unavailable`, or `unavailable`.
Repository and revision fields are present when Git can resolve them.
`all_committed` requires a nonempty list with every row committed.

The original wrapper hash and the expanded wrapper hash remain separate.
An unused upstream instruction model is omitted when an override replaces it.
Generated settings are bound by the settings hash. Generated RTL that is absent
from Git remains untracked. These records do not establish the generator inputs,
toolchain identity or adapter semantics. `source.identity_complete` stays false.
C4 never accepts bounded evidence, including when every copied input is committed.
Independent BOOM and VexRiscv adapter observations remain open under #63.

### Related clocks as periodic sampled schedules

Event BMC accepts repeated `--clock-schedule PORT=BITS` options. Declare every
clock, including `--clock`, or declare none. `clk=01` and `other=0011` describe
a 2:1 rate ratio. Rotate the bit strings to declare a phase. The leftmost bit is
sample zero. Each pattern repeats forever. Each must contain both levels and
2..256 samples. The joint period must not exceed 4096 samples. These are explicit
proof restrictions, not measured hardware clock relationships.

One solver step advances one global sample. The wrapper constrains clock levels
at that sample. The event backend samples property data before its triggering
edge; data that changes with a clock uses its previous sample at that edge.
Clock schedules do not add analog timing, delta cycles, jitter or events between
samples. When no schedule is given, the independent arbitrary-rate event model applies.
The existing reset harness still counts primary-clock edges. Async reset state
requires the separate `--async-reset` option. Unsupported state controls and raw
async-triggered properties remain refused. Replay and X flows remain unchanged.
`event_model.schedules` records the exact patterns; `relationships` states whether
the run used periodic schedules or unrelated clocks. Native phase tests require
both a passing same-phase reference and a failing opposite-phase reference.


### Nonzero latency example

`--latency 1 --unmatched-state prove --reset reset --settle 2` checks a
one-cycle candidate pipeline extension. Inputs remain identical on both sides at
every cycle. Eqy matches only boundary ports. Every output partition must pass
without internal state cutpoints. Native tests compare an independent one-stage
reference and two-stage candidate. They require proof at latency one and
counterexamples for latency zero, latency two and a changed arithmetic result.
The new option does not add memory maps, blackbox contracts or source-revision
export. Those parts of issue #18 remain open.


### Single-sample implication in native slang

The pinned native slang build applies `scripts/patches/slang-overlap.patch`.
It lowers `Boolean |-> Boolean` to `!antecedent || consequent` using the existing
SVA expression evaluator. Both sides use the same sample. The existing
`disable iff` condition gates the check. Inline assert and assume forms are
supported. There are no pending sequence threads in this subset.

The local import guard permits one top-level implication with Boolean operands.
It continues to reject `|=>`, delays, repetitions, nested or chained implications,
named properties and sequences before SBY starts. The frontend also rejects
unsupported AST forms, even without this guard. Use the source-built plugin;
the older OSS CAD Suite bundled plugin does not provide this extension.

Native positive and negative cases cover assertion, assumption and disable forms
on both qualified engines. The installer applies the patch after extraction of
checksum-pinned source archives. A failed patch stops the build. This extends
upstream lowering but does not provide full temporal SVA support or qualify
additional engines. Issue #61 remains open.

## Declared connectivity (#107)

Resolve required and forbidden connections from a captured SpinalDB database:

```sh
rvw formal connectivity connections.toml --db design.db --out /tmp/connections
rvw formal connectivity connections.toml --db design.db --out /tmp/connection-bmc \
  --run --depth 10 --timeout 60
```

Declare each connection in TOML. Use a unique ID. Mode and enable each name
one active-high Boolean signal. Both are optional. Their conjunction selects
the source sample. Latency defaults to zero.

```toml
[[connection]]
id = "selected-transfer"
kind = "required"
source = "io_source"
destination = "io_destination"
mode = "io_mode"
enable = "io_enable"
latency = 1

[[connection]]
id = "isolated-source"
kind = "forbidden"
source = "io_other"
destination = "io_destination"
mode = "io_mode"
```

The resolver uses the current SpinalDB schema and its standard name resolution.
It searches the complete destination cone. It retains data, selection, condition,
initialization, clock and reset dependencies. Missing or ambiguous endpoints,
opaque BlackBox cones and search limits remain incomplete. A shortest known
path cannot hide an alternate opaque path. Required value-transfer endpoints
must have equal widths. A dependency path is a candidate, not a temporal proof.
A missing path does not discharge mode, enable or latency conditions.

`--run` checks observed RTL contracts with the native formal runner.
The default is bounded. Select `--proof-mode prove` for an unbounded proof.
The clock must be one bit with synchronous active-high reset. Required
transfers can observe internal signals. Forbidden source, mode and enable
remain top inputs; its conditions must be distinct from source.
Required transfers compare the destination with the delayed source. The harness
delays mode and enable with that source. Reset clears delayed-valid state.
Forbidden influence uses two DUT copies. All inputs except source are shared.
Source values can differ at every cycle. The copies have independent initial
state. A passing result establishes the stronger bounded contract for these
states. A failing result can need initial-state triage. It is not a confirmed
source-influence bug. The mode/enable sample selects the comparison after the
declared latency; it does not constrain source differences at earlier cycles.

Each campaign retains separate transfer and activation jobs. Activation must
produce a counterexample after reset. Required transfers witness delayed
enable. Forbidden influence must also witness distinct source values sampled
with that enable. The source difference is delayed with the condition. A
transfer pass without this activation witness remains incomplete. Both jobs must retain
exactly one assertion. The BMC runner also checks bounded reachability before
it reports a pass. Each RTL file must match its database content hash. The
runner retains copied inputs, native tool identities, logs and counterexamples.
Timeouts and tool errors cannot earn a bounded pass.

`result.json` uses `rvw.connectivity/1`. Each entry retains the declaration,
resolved endpoints, structural path or absence, conditions, limits and optional
campaign observations. `semantic_status: bounded_pass` describes only the stated
two-state bound under captured DUT assumptions. Overall `status` remains
`incomplete`, and exit code is 1. This command supplies no design acceptance verdict.
Invalid input exits 2. Use a fresh output directory for each campaign.

Internal forbidden influence and core qualification remain open. Inouts,
asynchronous resets and multiple clocks need another backend. Unbounded
results apply only to the stated connection contract and captured assumptions.
No whole-core proof or commercial parity is claimed.

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
## Engine benchmark protocol

The manifest uses `rvw.formal-bench/1`, with nonempty `cases` and an optional
`baseline` engine. Each case declares `id`, `top`, `clock`, `reset`, `mode`
(`bmc` or `prove`), `depth`, and `sources` rows with `path` and `sha256`.
Paths are relative to the manifest. All hashes must match before execution.
Only self-contained exported RTL is supported. The committed suite has a
handwritten HWMCC-style finite-state counter, its seeded property fault,
and a handwritten RV32 arithmetic fixture. These are small protocol fixtures. They are not HWMCC competition
entries or results on a processor.

The runner executes each installed supported engine separately and serially.
It tries SMTBMC with Yices, Z3, Bitwuzla, Boolector, CVC4, CVC5 and MathSAT;
ABC BMC/PDR; Avy; and BTOR with pono/btormc. An incompatible mode is explicit.
Other engine adapters, including rIC3 and EBMC, remain open. Tool identities
and native logs stay in each run directory. Engine errors remain errors.

Wall time measures the complete CLI command, including capture, elaboration
and reachability checks. Peak RSS comes from native `/usr/bin/time` (bytes on
macOS; KiB converted to bytes on Linux). It is the operating system's process
measurement, not a sum of simultaneous solver memory. Missing measurements
are null. Reached depth is the largest assertion-check step explicitly logged
by SMTBMC. Other engines currently report null. Requested depth is separate.

Agreement requires at least two decisive results and no unresolved installed
run in that mode. A disagreement overrides unknown results. Pair comparisons
require a decisive matching verdict for every case. They use the worst candidate
wall-time ratio against the baseline. The 5% margin is a descriptive threshold.
`noninferior_on_suite` and `superior_on_suite` apply only to this run. They are
not statistical claims, commercial parity claims or correctness oracles.

An optional `adapters` array selects a licensed engine. Each row has a unique
plain `id` and an absolute executable `command`. It must support `--version`.
The runner calls `COMMAND REQUEST.json RESPONSE.json` with a timeout. The request
has schema `rvw.formal-adapter-request/1`, the case, and frozen source paths.
The adapter must write `rvw.formal-adapter-response/1`, `request_sha256` (SHA-256
of the exact request bytes), `mode`, `status` (`pass`, `fail`, `inconclusive`),
`engine_version`, `wall_s`, `peak_memory_bytes` and `reached_depth`. Measurements
must be finite and nonnegative. For a BMC pass, `reached_depth` must be an
integer at least `depth - 1`, the last requested zero-based assertion step.
A shorter successful prefix remains inconclusive. Missing fields or a request mismatch stay
inconclusive. The adapter owns licence setup and source translation. These are
trusted adapter observations, not independently replayed proofs. No licensed
engine is bundled. Published-result normalization and repeated statistical
experiments remain open.

### Exported core leaf checks

`SpinalChecks/examples/apps/export_leaves.py` takes `--vex-rtl VexRiscv.v`,
`--boom-rtl BoomSimTop.v` and a fresh `--out DIR`. It copies the generated
`StreamFifo` and `ForwardingAgeLogic` modules without changing their equations.
It prints SHA-256 identities for the full inputs and leaf files. It does not
elaborate either core or certify the source revision of supplied RTL.

Run `rvw formal apps DIR/vex.json --depth 10 --event-model --async-reset --out VEX_OUT` under the `vex`
lock. Run `rvw formal apps DIR/boom.json --depth 10 --out BOOM_OUT` under the
`boom` lock. The properties check that FIFO occupancy and availability cannot
both be one, and that forwarding `found` agrees with the prior cycle's nonzero match vector.
The VexRiscv FIFO needs the sampled-event model because its reset is asynchronous.
These are small exported leaf invariants. They are not whole-core verification,
full CSR or connectivity checks on these processors, or a performance benchmark.


Depth search records its engine selection and termination reason. It doubles
`--depth` up to `--max-depth` under `--budget`. It stops at the first result
other than pass. The largest passing bound remains a bounded observation.


## Simulation-state swarm

```
rvw formal swarm --verilog top.sv --top top --trace wave.vcd \
  --start-cycle 1 --end-cycle 100 --samples 4 --depth 12 \
  --budget 120 --timeout 25 --out /tmp/swarm
```

The command needs explicit RTL and top arguments. It captures RTL, includes,
checks and trace once. It selects distinct cycles at uniform intervals, including
both endpoints when samples exceed one. Tasks run in sequence to bound machine
load. Each uses the existing from-sim guards and a separate reachability check.
The budget starts after input capture. Each timeout is capped by the remaining
budget. Capture and frontend overhead can exceed the budget.

The aggregate always exits 1 with `inconclusive`. Per-state passes apply only to
that state and depth. Trace states have no checked reset reachability or design
identity. Failures are conditional counterexamples. Missing state stays free.
Every attempt retains restrictions and loaded-state coverage. Remaining cycles
are explicit if the budget expires. This selection does not establish coverage,
property activation, typed-cone selection or an unbounded proof. `--memories free`
keeps all initial memory words free; trace mode loads available words. Zero fill
is excluded from this command.


## Exact proof reuse

`bmc` and `prove` accept `--proof-cache DIR`. The cache shares retained successful
SBY evidence through a local or mounted directory. It skips only the main engine
job. Each invocation still captures inputs and tools, elaborates the design,
checks clocks and state controls, runs fresh reachability, and verifies tools.

The dependency rule requires identical complete prepared input artifacts,
property and environment restrictions, proof script and depth, captured file
hashes, tool payloads and versions, captured environment, Python executable and
version, and formal/common runner code. Only the owned output path prefix is
normalized. Other source paths and locations remain significant. A changed cone,
assumption, property, relevant design input or tool therefore misses. An unrelated
file outside these dependencies can change without invalidating the entry.
This is conservative whole-model reuse. It does not infer per-property cone
independence or reuse across a design change.

Only pass results with assertions and successful reachability enter the cache.
Entry hashes protect retained artifacts against accidental changes. Corrupt or
incomplete entries miss. Entries are published by directory rename. Share only
trusted directories under C8. This is not an authenticated remote cache. There
is no automatic eviction or repair of a corrupt entry; remove it to republish.
Cache-hit wall time describes current work. It does not measure original proof
cost or establish a speedup.


## Memory encoding

`bmc` and `prove` accept `--memory-model auto|array|map`. Auto keeps the SBY
backend choice. Array requires an SMTBMC-only portfolio and retains RTL memories
for the SMT array backend. Map inserts `memory_map -formal` before the engine.
`memory_model.retained_memory_cells` reports remaining `$mem_v2` cells in the
prepared design. Optimization can remove a memory completely. This count does
not establish RAM refinement.

Both modes preserve the frontend's RTL initialization, ports and collision
semantics. They add no memory abstraction assumptions. Undefined contents and
read-under-write behavior stay under Yosys semantics. Blackbox memories need a
separate refinement contract; this option cannot prove that contract. Native
legal and faulty RAM tests check both encodings. No capacity gain is claimed.

## Hardware leakage checks

`rvw formal security` runs bounded Spike contract comparisons and emits mapped-gate
IFT instrumentation. See [security/README.md](security/README.md) for the hardware
threat model, adapter contract, sampled ADD timing scope and explicit limits.

### Solver cores

`rvw formal proof-core --smt2 query.smt2 --mapping bindings.json --out core`
extracts a solver core with Z3. Each assertion must use `(! TERM :named LABEL)`.
The command checks the core again and removes each constraint when the remaining
query stays unsatisfiable. It reports deletion minimality, not minimum size.
Unknown checks keep the constraint and disable the minimality claim.

The mapping has schema `rvw.smt-bindings/1`, a stable `property_id`, optional
`requirement_ids`, and `constraints`, an object from each label to its design
binding. Each binding can contain `signals` and source metadata. `--db design.db`
resolves those signals with the same SpinalDB reader as `rvw query`. Unresolved
signals and database staleness remain visible. The input query, mapping, database,
solver identity and every reduction query are retained. MCP: `formal_proof_core`.

This command accepts a single non-incremental SMT query exported by a solver
flow. It does not convert arbitrary AIGER proofs or infer an induction query from
an SBY PASS. Unsatisfiability applies to this query only. It does not authorize
coverage exclusions. Use `rvw cov prove` for the existing guarded UNR export.
`rvw formal power --intent intent.json --out generated [--db design.db]`
generates sampled clock-gating, isolation, retention, test isolation and supply
transition checks. `formal_power` is the MCP entry point. It can resolve declared
DFT access paths from SpinalDB. Read [the intent contract and limits](../../../../SpinalChecks/power/README.md).
Generation does not run proofs, ATPG or physical power analysis.

`rvw formal csr --model project-csr.json --out generated` writes CSR formal
monitors, optional project-bound SBY jobs, directed assembly and functional
coverage groups. `formal_csr` exposes the same generator through MCP.
See [the CSR format and limits](../../../../SpinalChecks/csr/README.md).
Generated files carry no proof or compliance verdict.

The `template` command also supports `hpm`, `initialized_read` and `axi_lite`.
Set `--width` for the counter or initialization mask width.
The HPM monitor starts from zero and uses independent event multiplicity,
inhibit/filter controls, accepted writes, sticky overflow and interrupt enable.
Counter writes suppress a new overflow. Clear has final pending priority.
This is a declared project interrupt policy, not universal Zihpm behavior.
Access permissions and RV32 halves use the existing Spinal HPM helpers.
The initialization monitor tracks written bits. A used read must have all its
required read bits initialized before that edge. Same-edge writes do not bypass.
The AXI-Lite monitor has one outstanding address/data pair and one read.
AW and W can arrive independently. Responses need prior accepted requests.
It checks handshake observations and rejects EXOKAY responses. It does not check
payload stability, response data, or full AXI/TileLink behavior.
Bind each monitor from a project wrapper, then use the existing formal flows.
Native fixture results are bounded observation checks, not whole-core proof.
### Properties beside Spinal RTL

`spinalchecks.Sva` emits the same module-local SVA consumed by the temporal
frontend. It supports finite sequence composition, sampled-value functions,
unbounded repetition, explicit strong or weak sequences, `s_eventually` and
the Boolean `until` family. The selected lowering route keeps its own limits.
Render after Spinal assigns RTL names, then include the snippet in the reviewed
module or checker wrapper. See [the Scala API](../../../../SpinalChecks/README.md#scala-property-builder).
The builder does not insert properties into a design or run verification.

### Resource-aware scenarios

`formal scenario plan` schedules explicit logical actions with resource claims,
data dependencies and backend-specific timing. `formal scenario check` compares
supplied outcome records. Neither command executes backend operations. See
[the scenario contract and PSS reuse assessment](SCENARIOS.md).

### Finite PSL adapter

```sh
rvw formal psl properties.psl --clock clk --out properties.sv
```

The adapter accepts a finite Verilog-flavor PSL subset. It emits SVA statements
for inclusion inside a project module. A file can instead declare
`default clock = (posedge clk);`. Supported directives are `assert always`,
`assume always`, and `cover` with a finite SERE. Boolean implication, `next`,
`next[N]`, flat SERE concatenation, finite consecutive repetition and suffix
implication map to the shared finite SVA frontend. Every emitted statement is
checked by that frontend before publication. `formal_psl` provides the same
operation through MCP. Generation does not run verification.

Nested SEREs, verification units, multiple clocks, unbounded repetition, abort
and PSL liveness operators remain refused. This is not full PSL conformance.
The syntax and sampling reference is the
[Accellera PSL 1.1 manual](https://www.inf.pucrs.br/calazans/graduate/SDAC/PSL-v1.1.pdf),
sections 4.4, 5.4 and 6. Native tests check legal and faulted next-cycle and suffix
implications through the emitted SVA and SMTBMC/Yices.

## Finite temporal SVA and task regression

Use open Yosys for RTL and immediate formal statements. The `temporal` frontend
adds finite sequences that the installed slang plugin cannot lower:

```sh
rvw formal sva-lower properties.sv --out lowered.sv
rvw formal bmc --frontend temporal --verilog properties.sv --top Top --out proof
rvw formal regress suite.toml --jobs 2 --timeout 60 --out campaign
```

The frontend supports module-local named sequences without arguments, Boolean
atoms, `##N`, `##[M:N]`, consecutive `[*N]` and `[*M:N]`, sequence `or`,
`|->`, `|=>`, `disable iff`, and inline `assert`, `assume`, `cover property`.
Each implication has one sequence on each side. Overlapping starts and all
antecedent matches create separate obligations. Checks wait for the latest
finite consequent deadline. Bounds are at most 64 samples, with at most 512
expanded paths. Zero-length repetitions are refused. There is no implicit
fairness assumption. Unbounded liveness,
nonconsecutive repetition, nested implication, clocking blocks, macros, parameterized
properties, and action blocks give `unsupported:CONSTRUCT` diagnostics.
The slang frontend retains its separate qualified sampled-value subset.
No licensed tool is required. sv2v does not supply temporal assertion lowering.

Sampling is the value before each rising edge in the Yosys formal event model.
This does not implement all SystemVerilog simulator scheduling regions.
`disable iff` clears the validity history asynchronously. With delayed properties,
use `--event-model --async-reset` for the generated asynchronous state. A reset
pulse sampled between clock edges cancels pending checks. Pulses wholly between
global samples remain outside the model. Separate property statements can use
separate clocks. A sequence cannot change clocks. General async-triggered SVA
remains unsupported. BMC needs enough samples after a start to reach its deadline;
a bounded pass does not discharge later obligations.

Native semantic tests exercise each finite construct with a legal design and a
seeded fault on SMTBMC/Yices. ABC BMC3 also runs these fixtures. Four legal
fixtures optimize to combinational logic, which ABC BMC3 refuses. Those native
errors are checked as errors; they are not proof results.

A regression manifest declares one assertion per task:

```toml
[[property]]
id = "response_bound"
sby = "checks.sby"
task = "response"
top = "Top"
requirements = ["REQ-1"]
assumptions = ["reset starts active"]
config = "small"
```

SBY `[tasks]`, task tags and negative task tags select one resolved job per row.
Python configuration blocks and engine portfolios are refused. One SBY engine
process runs per worker. `--jobs` is capped by the detected CPU count. This is a
worker cap, not an OS limit on threads inside a solver. Listed sources, jobs and
tool bindings are captured before execution. Transitive input closure and full
property attribution remain uncertified. To select the manifest from project
data, set `[formal] regress = "suite.toml"` in `rvw.toml` and omit the argument.

`results.json` uses C3. Each row retains the task, requested BMC depth, trace
paths, and `formal_status`: `proven` (conditional unbounded engine result),
`bounded-pass`, `failed`, `unknown`, `timeout`, `unsupported`, `vacuous`, or
`error`. An explicit solver PREUNSAT result is `vacuous`. Without a separate activation cover job, activation remains `not_measured`. A bounded pass is never `proven`.
The suite remains inconclusive and exits 1. JUnit records conditional observations
as errors, so CI cannot treat them as accepted design proofs. `result.json`
is the summary returned by the `formal_regress` MCP tool. `formal_sva_lower`
provides the lowering command through MCP.

## Common SVA intents and typed channels

`rvw formal properties intents.json --out checks.sv` writes SVA snippets for
insertion inside the module that owns the declared signals. Feed the combined
source to `sva-lower` or `bmc --frontend temporal`. MCP `formal_properties`
provides the same operation. Generation does not prove the design.

```json
{"properties": [
  {"id":"tx", "kind":"handshake", "clock":"clk", "reset":"rst",
   "valid":"valid", "ready":"ready", "payload":"payload", "width":8},
  {"id":"reply", "kind":"request-response", "request":"req",
   "response":"ack", "minimum":1, "bound":8}
]}
```

Available intents:

| Kind | Contract and fields |
|---|---|
| `handshake` | Hold `valid` and `payload` after a stalled sample. Declare `valid`, `ready`, `payload`, `width`. |
| `fifo` | Count range, overflow, underflow and exact count transition. Declare `count`, `push`, `pop`, `depth`, `width`. Push and pop mean accepted transfers. This does not check FIFO data order. |
| `one-hot` | At most one bit. Declare `bits`; `allow_zero: false` also requires a bit set. |
| `arbiter-fairness` | Every sampled `request` gets `grant` within `minimum..bound`. This is a finite response contract, not general fair liveness. |
| `request-response` | Every sampled `request` gets `response` within `minimum..bound`. It does not match transaction IDs or count responses. |
| `flow` | Payload is at most `max_value` when `valid`. Declare an explicit `max_value`. Flow has no backpressure, so no hold contract is inferred. |

Each intent has an `id`, an optional `clock` (default `clk`), and an optional
active-high `reset`. A delayed reset contract needs the asynchronous event model
described above. Each intent can use a different clock. There is no cross-clock
sequence or inferred relationship between clocks. Use existing periodic clock
schedules to declare ratios and phases in global samples.

`--channels top.checks.json` reads the actual Stream/Flow channel types from
`rvw.checks/1`. The positional JSON file then maps each `path.object` to its
reviewed clock, reset, local port mapping, payload width and intent ID:

```json
{"Top.io_tx": {"id":"tx", "clock":"tx_clk", "reset":"rst", "width":8,
 "ports":{"Top.io_tx_valid":"valid", "Top.io_tx_ready":"ready",
          "Top.io_tx_payload":"payload"}}}
```

The generator requires bindings because the channel report does not carry a
unique domain or payload width. It does not infer a clock from signal suffixes.
Missing bindings and multi-leaf payloads give named unsupported diagnostics.
Flatten a composite payload explicitly before binding it. Existing SpinalChecks
elaboration-time assertions remain available. This generator emits SVA from
exported type metadata; it does not change Spinal RTL or assign a domain inside
mixed-domain components.

Native event tests include properties on two distinct sampled clocks and a
reset pulse between rising edges, with pass/fail mutants. Multi-clock replay
from simulation state, X analysis, mixed-domain elaboration metadata, raw async
property events and additional async state types remain open under #46.

### Finite sequence composition and sampled values

The temporal frontend supports finite `throughout`, `within`, and `intersect`.
`intersect` requires equal endpoints. `within` permits each complete placement
of the inner sequence in the outer sequence. `throughout` requires a Boolean
left operand at every sample of the right sequence.

Single-argument `$past`, `$rose`, `$fell`, `$stable`, and `$changed` use the
property clock. Edge functions use bit zero. Stability functions compare the
full vector. History before the first event is unconstrained in formal.
`$past(expr, N)` supports positive decimal depths from 1 to 64. Nested sampled
calls are supported to a depth of eight. Sampled calls in `disable iff`, gated
history and explicit alternate clock arguments remain refused. No cross-clock
history or full simulator scheduling is claimed.

Historic values retain the source expression width and signedness. In Icarus,
edge functions use four-state case comparisons. Stability functions compare all
bits, including X/Z. Formal initial history remains unconstrained. This does not
qualify every typed initialization or simulator scheduling region. The Scala
builder exposes explicit depth as `.past(N)`.
The [support table](TEMPORAL_SUPPORT.md) is generated from the semantic test
corpus. It records test scope, not a complete SystemVerilog conformance claim.

Finite `first_match` excludes every earlier matching endpoint. It retains ties
at the first endpoint. The same path and delay capacity limits apply.
Run `python3 scripts/formal-support-table.py` to regenerate the table.

### Typed finite local captures

Named properties can declare packed `logic`/`reg` variables or 32-bit
`int`/`integer` variables. Signed and unsigned declarations retain their type.
A Boolean antecedent can capture one or more design expressions:

```systemverilog
property response;
  logic [31:0] sent;
  @(posedge clk) (req, sent=data) |=> ack && result==sent;
endproperty
check_response: assert property (response);
```

Each attempt uses clock history for its own captured value. A later request
cannot overwrite an earlier attempt. The consequent can use the existing finite
sequence operators. Capture-to-use distance is limited to 64 clock ticks.
The lowering report includes optional `local_variables` width/signedness data.

Assignments run in capture-list order. A later assignment can read a local
that an earlier assignment set. Each assignment applies the local's declared
width and sign before a later assignment reads it. Reassigning a local does not
change a value already used by another local. For example,
`(req,v=data,w=v+4,v=v+1)` retains the earlier `v` value in `w`.
A dependent assignment can select bits from an earlier local value.

This subset requires one Boolean capture antecedent and one implication.
Reads before assignment, initialized declarations, flow-sensitive antecedents,
local slices in the consequent, sampled uses of locals and additional
local types remain refused. Local clocks and local reset conditions are refused.
The same lowered captures run in formal and native simulation. This is not full
local-variable flow or SystemVerilog scheduling qualification.

### Named properties and checker bindings

The temporal frontend accepts module-local, argument-free named properties.
Each referenced declaration must resolve to an explicit rising-edge property.
Recursive references and unused named-property declarations are refused.

Checkers with explicit ANSI input ports can bind to a module type with named
port connections. Each instance of that module gets the checker instance.
For separate files, pass both files to BMC:

```sh
rvw formal bmc --frontend temporal --verilog dut.sv checks.sv --top dut --out proof
```

The input snapshot retains both source files. It seals one combined lowered
file before the native frontend reads it. Instance-target binds, checker output
ports, event arguments, default arguments and positional binds remain refused.
Checker port and RTL type errors remain native frontend errors. The lowering
does not infer an environment contract or qualify simulator scheduling regions.




`rvw formal proof-core --result RUN --out DIR` exports a bounded SMT query
from `RUN/sby/model/design.il`. It also works when the captured SBY job used
an AIGER engine. No hand-written SMT is needed. Use `--depth` to set the sample
count. The core groups initial state, transitions, hierarchy and assumptions
by sample. It checks all assertions together. It does not identify minimal
logic cells or establish an unbounded proof. SAT and solver errors remain
inconclusive. The existing `--smt2` and `--mapping` mode remains available.
Use `--property CELL_NAME` to select an exact assertion from the captured top.
The generated bindings retain its cell name as the property ID. Without this
option, all assertions are checked together. A separate bounded feasibility
query must be SAT. A conflicting environment remains inconclusive and retains
its solver core in `environment_core`.


### Captured assertion enable measurements

Captured-model proof cores also measure each recognized Yosys assertion enable
guard. `property_activation` reports reached, not reached within the bounded
model, or inconclusive. A blocked guard retains a reduced blocking core and
its assumption cells. This can identify assumptions that prevent a procedural
check from running. It does not analyze every logical antecedent in a property
or establish complete non-vacuity. Environment feasibility remains separate.

The testplan HTML includes module summaries, core status and labels, cell
coverage availability, activation and source locations. A core evidence row can
supply `property_id` as an explicit alias for an inventory ID. The report retains
the native ID as `captured_property_id`. This mapping is declared input, not an
automatically verified semantic equivalence.

## Engine portfolio and explicit-model proofs

`rvw formal engines --out OUT` reports optional engine dependencies. Installer
checks with `scripts/install.sh --with-formal --check` also list these tools.
Missing optional tools report `not_installed`. They do not block the base install.

`rvw formal engine-race --manifest examples/formal/deep/race.json --out OUT`
races installed SBY engines and EBMC on the same captured, hash-pinned RTL.
The source must include its assertions, clock semantics, initialization and
assumptions. Literal includes and external memory data are not supported here.
Yosys must find an elaborated assertion. No clock, reset or vacuity guard is
added by this raw engine experiment. Source assumptions remain restrictions.
A portfolio proof with source assumptions stays inconclusive because activation
is not checked here. Use the guarded proof and contract flows for those jobs.
The first conclusive answer wins. Other process groups stop. Use `--cross-check`
to keep engines running until they answer or reach `--timeout`. Conflicting
answers make the final result inconclusive. A missing or cancelled answer does
not establish agreement. Bounded success never wins an unbounded proof race.

Adapters cover SBY SMTBMC/Yices and Z3, ABC PDR and BMC3, Pono BMC, Avy,
rIC3, and direct EBMC BMC/k-induction. SBY must support the selected backend.
An old SBY backend, a crash, or an unrecognized result reports an error.
The rIC3 adapter follows the upstream SBY
[aiger adapter](https://github.com/YosysHQ/sby/blob/main/sbysrc/sby_engine_aiger.py).
EBMC uses its documented `--k-induction` and `--bound` options.

`rvw formal engine-bench --manifest examples/formal/deep/seeded.json --out OUT`
runs every engine/case pair separately. It records each engine command, executable
hash, source hashes, result and wall time. Requested depth is not reached depth.
The committed suite contains a safe counter and a seeded overflow fault. Supply
other self-contained exported suites with SHA-256 source entries. No HWMCC data
is bundled. No speedup or commercial capacity claim follows from these fixtures.

`rvw formal model-grid --manifest MODEL.json --out OUT --workers 4` splits
properties of an explicit finite transition system across local workers. A model
has `states` mapping state IDs to integer fields, `initial` state IDs, `edges`
with pairs of state IDs, and `properties` mapping names to bad state IDs.
Dead ends have no successors. All nondeterministic choices must be explicit.
Optional `visible` fields seed CEGAR localization. Optional `samples` contain
integer state observations for `--method induction`. The default CEGAR method
projects state fields, searches the quotient graph, replays each abstract trace,
and adds a field after a spurious counterexample. RAM words, counters and cut
signals can be fields. Hidden fields give an existential overapproximation.
The refinement limit leaves a spurious result inconclusive.

Induction checks the reachable base and the k-step condition over all states.
It mines ranges, pairwise order and constant differences. Each helper needs an
independent initiation and consecution proof. Failed helpers are discarded.
These algorithms prove only the supplied graph. They do not extract an RTL
transition graph or certify a memory/RTL translation. Use the existing
`formal contracts` command for typed module contracts, provider checks, cycle
rejection and the final closed composition proof.

Add `--hosts hosts.json` to `model-grid` to run one local shard and one shard
per configured host. Host records use the farm fields `name`, `address`,
`python`, `ssh_options`, `resources` and `limits`. Remote hosts need the same
installed adapter source. The adapter checks source identities, payload hashes,
artifact hashes and property coverage. It uses the existing `rvw.farm.worker`
SSH endpoint, resource reservations and cancellation. Its payload is JSON in the
farm's byte transport field. It does not create a simulation C1 result.
Tests exercise that endpoint locally. Real SSH distribution was not tested.

Set a source `format` to `aiger` for a binary or ASCII AIGER safety model.
The importer preserves latch initialization, unconstrained initial latches,
bad-state predicates and invariant constraints. It rejects justice, fairness,
and mixed ordinary outputs/bad predicates. Legacy outputs are bad predicates.
The original bytes and translated RTL remain in the run directory. EBMC is
excluded from this input mode because the translation uses Yosys global-clock
semantics.

The pinned manifest `examples/formal/deep/hwmcc-small.json` selects two small,
preprocessed competition problems from the CAV 2025 artifact at a fixed commit.
Download their bytes outside the repository:

```sh
rvw/.venv/bin/python scripts/fetch-formal-bench.py examples/formal/deep/hwmcc-small.json --out /tmp/rvw-hwmcc
rvw formal engine-bench --manifest /tmp/rvw-hwmcc/manifest.json --out /tmp/rvw-hwmcc-results
```

This subset is a smoke sample. It does not measure full-block proof capacity.
The native smoke retained Avy and SMTBMC errors instead of treating them as
agreement. No result is promoted to commercial parity.

## Automatic RTL refinement and relational helpers

`rvw formal rtl-refine --manifest examples/formal/deep/race.json --out OUT`
selects internal state and RAM read-output nets as unconstrained cuts. It uses
the existing guarded proof runner. SMTBMC/Yices is the default engine. Each
abstract counterexample restores one driver and starts a fresh proof. Only a
cut-free counterexample reports failure. A proof of the overapproximation can
report unbounded success. Budgets and tool errors leave the result inconclusive.
An ABC witness-replay error on an abstract model also remains inconclusive.
The source manifest uses the same pinned RTL entries as engine-race. Optional
fields are `engine`, `clock`, `reset` and `depth`. This is driver restoration,
not a synthesized RAM collision contract or arithmetic counter summary.

`rvw formal relation-strengthen --manifest CONTRACT.json --out OUT` uses the
existing strengthening manifest. It adds pairwise equality, order, constant
offset and mutual-exclusion candidates to observed unsigned bounds. Every
candidate needs a separate fresh unbounded proof. Rejected candidates cannot
strengthen the target. Certified candidates remain assertions in the final
joint induction job. Offset candidates use Verilog bit-vector arithmetic.
Trace observations alone never prove a helper.

`rvw formal rtl-grid --manifest examples/formal/deep/seeded.json --out OUT --workers 2`
splits exported RTL safety problems across local workers. Add `--hosts` with
farm host records to add remote shards. Each case has its own top module,
properties, source hashes and engines. The controller bundles the source bytes
once. Farm workers verify bundle and adapter identities before running each
case. The source assumptions and activation limits of engine-race still apply.
Use `engine_timeout` in the manifest to limit each engine. A missing remote
answer leaves its assigned properties inconclusive.

If cut-free SMT induction is inconclusive, RTL refinement tries ABC PDR with
the remaining budget. This is a fresh proof, not reuse of a failed induction.

## Native engine diagnostics

Run `rvw formal doctor --out OUT --json` to list dependencies and enabled adapter
features. The `formal_doctor` MCP tool returns the same data. Installed tools
remain unqualified until a native benchmark runs. Bitwuzla and cvc5 are optional
SMTBMC backends. `btor:btormc` enables bounded search. `aiger:suprove` enables
unbounded safety when its external executable is present.

Use `scripts/install.sh --with-ric3` or `--with-ebmc` for pinned source builds.
Builds use two jobs at low priority under `~/.cache/rvw/formal-engines`.
rIC3 uses a pinned Rust nightly. EBMC needs a C++ compiler, GNU make, flex,
bison, curl and patch. Source revisions and native build commands are in
`scripts/install-formal-engine.py`. Source this checkout's `env.sh` after install.
`--check` probes the selected executable. A successful probe is not proof
qualification. Existing OSS CAD Suite installs supply pono, Avy, Bitwuzla, cvc5
and Yices; their native benchmark results must be checked separately.

Native measurement on macOS ARM64, 2026-11-13, on the two pinned cases in
`examples/formal/deep/hwmcc-small.json`. Each engine ran alone with a 12 s
timeout. Times below sum engine execution time, excluding preparation.
This small subset does not establish full-block capacity.

| Engine | Solved / 2 | Engine time (s) | Outcomes |
|---|---:|---:|---|
| `abc:pdr` | 2 | 4.797 | pass, pass |
| `smtbmc:yices` | 1 | 7.108 | pass, inconclusive |
| `smtbmc:z3` | 1 | 4.910 | pass, inconclusive |
| `smtbmc:cvc5` | 1 | 7.278 | pass, inconclusive |
| `smtbmc:bitwuzla` | 1 | 5.920 | pass, inconclusive |
| `aiger:avy` | 0 | 4.233 | error, error |
| `aiger:rIC3` | 0 | 0.000 | not_installed, not_installed |
| `aiger:suprove` | 0 | 0.000 | not_installed, not_installed |
| `ebmc` | 0 | 0.000 | not_installed, not_installed |

Raw results and tool hashes: `/tmp/rvw-deep-hwmcc-run2/result.json`.
Avy crashed. Induction exhaustion stays inconclusive. Missing engines were
not run. No licensed comparison or open-core property campaign ran.


### Unbounded temporal properties

```sh
rvw formal liveness response.sv --top dut --out live-job
rvw formal liveness response.sv --top dut --out live-job --run --timeout 60
```

This command accepts `assert property (@(posedge clk) req |-> s_eventually ack)`
and the corresponding `assume` form. A bare `s_eventually ack` uses a constant
request. Each pending request remains pending until a sampled acknowledgement.
The generated SBY job uses native `$live` or `$fair` cells and `aiger suprove`.
The same response can discharge all earlier identical response obligations.
No finite deadline replaces eventuality. The clock is one abstract rising-edge
clock. Reset cancellation, cross-clock properties and mixed finite/liveness jobs remain
refused. The additional temporal forms below use dedicated progress automata.

Without `--run`, the command writes a job and reports `observation=not_run`.
With `--run --backend suprove`, a missing SBY or suprove gives `missing_tool`. Engine passes remain
`status=unknown` because attribution, activation and non-vacuity are not certified.
An engine failure is recorded as a failure. `formal_liveness` exposes the same
operation through MCP. Native lowering tests check `$live` creation. Those tests
do not qualify an engine. The `l2s` route below has separate native checks.
The same command accepts Boolean `until`, `until_with`, `s_until` and
`s_until_with`. Exclusive `until` does not test the left operand at the completion
sample. Inclusive `until_with` does. The `s_` forms require eventual completion.
Both `|->` and `|=>` are supported for a Boolean antecedent. Zero-argument named
properties and module-local aliases are accepted. A named property carries its
own explicit clock. Recursive references, duplicate names and unused property
declarations remain refused. Property arguments and local captures remain
outside this unbounded subset.

Supported unbounded sequences are `a ##[M:$] b`, `a[*M:$] ##1 b`,
`a[*] ##1 b`, `a[->N]` and `a[=N]`. Goto and nonconsecutive counts can also
use positive literal ranges such as `[->1:3]` or `[=1:3]`. They can have
one `##1 b` completion. Operands must be Boolean expressions. Counts are positive
decimal literals and state or delay limits are 64. A consecutive repetition with
no completion must have a positive minimum. An optional outer `first_match`
selects the same existence condition for these standalone consequents.

Sequence consequents in assert and assume default to `weak(...)`.
Use `strong(...)` to require a match. The lowering preserves this distinction.
For example, `req |-> b[->2]` can wait forever. `req |-> strong(b[->2])`
requires two sampled `b` events for every request. Overlapping requests use
count buckets. A separate set tracks old obligations until they complete.
New requests cannot erase those obligations or prevent acceptance forever.

A count range retains every permitted completion. For example,
`b[->1:3] ##1 c` can use the second or third occurrence when the `c` sample
after the first occurrence is false. It fails when the final permitted occurrence
cannot complete. Nonconsecutive repetition can wait through additional `!b`
samples before `c`. A standalone range needs only its minimum permitted count.
The maximum is at most 64, or 63 when there is a completion operand. Zero-count
and unbounded-count ranges remain refused.

A Boolean `g throughout sequence` modifier is accepted around these unbounded
sequence forms. The guard holds from each request through its accepted endpoint,
including that endpoint. A false guard during an active attempt makes the
sequence impossible. A false guard after completion does not affect that attempt.
Nested guards combine. Outer `first_match` wrappers can surround or follow the
guard. Weak sequences still permit waiting forever, but their guard must hold
while they wait. Result rows mark this modifier with `throughout=true`.

The rules follow IEEE 1800-2017 clauses 16.9 and 16.12, including the weak default
for sequence properties. The [IEEE language reference](https://rfsoc.mit.edu/6S965/_static/F25/documentation/1800-2017.pdf)
gives the operator definitions. The generated support table includes paired native
cases for each listed form. General nested sequence composition,
reset cancellation and local captures in this unbounded frontend remain refused. Native finite checks need a separate job.

Unbounded operands can use the same clock-local `$past`, `$rose`, `$fell`,
`$stable` and `$changed` history as finite properties. This includes request and
response operands and Boolean units within supported repetitions. `$past` accepts
a decimal depth from 1 to 64. Nested history is limited to eight levels. History
retains the source width and sign. Rose/fell test the least significant bit.
Stable/changed compare the full value with four-state equality. History before
the first sample is unknown. Multi-clock history, gated sampled calls and local
variable history remain outside this route.

### SVA liveness through safety engines

```sh
rvw formal liveness response.sv --top dut --out live-proof --run --backend l2s --reset reset
rvw formal liveness response.sv --top dut --out live-search --run --backend l2s --reset reset --mode bmc --depth 20
```

The `l2s` backend reuses the finite-state RTL liveness-to-safety runner.
It exposes generated SVA progress predicates and checks one assertion per job.
Assumed eventual-response properties become explicit justice predicates.
`prove` defaults to ABC PDR. `bmc` defaults to SMTBMC/Yices and searches bounded
lassos. A bounded passing search is not a liveness proof.

This route requires one synchronous clock, a scalar active-high reset input and
zero-based descending net ranges. The harness applies one startup reset cycle
and then keeps reset deasserted. The existing engine still refuses unsupported
state and black boxes. It snapshots the full converted state, including progress
monitors. Fairness feasibility and activation are not certified.

Each job retains the native runner's result, proof kind, converted state-bit
count and limits. An engine pass remains frontend `status=unknown`. A failed
lasso makes the frontend fail. The default `suprove` route remains available.
`--backend l2s` requires `--run` because native model export is part of that route.
The `formal_liveness` MCP tool accepts the same backend, reset and safety options.


## State selection and fair finite models

`rvw formal swarm` accepts `--state-plan PLAN.json` and repeated `--engine-pool`
options. A plan binds the trace SHA-256 to coverage-hole priorities:

```json
{"trace_sha256": "SHA256", "holes": ["full", "wrap"],
 "states": [{"cycle": 5, "targets": ["full"]},
            {"cycle": 17, "targets": ["wrap"]}]}
```

Use `--start-cycle`, `--end-cycle`, and `--samples` to bound the selection.
The runner chooses states with the most remaining targets. It rotates engines
across the chosen states. Existing `--depth`, `--timeout`, and `--budget` bound
the searches. Supplied target labels do not prove cover reachability. Sampled
states do not establish reset reachability. The campaign stays inconclusive.
MCP `formal_swarm` exposes the same options.

`rvw formal model-live --manifest MODEL.json --out OUT` checks recurrent progress
on the explicit models used by `model-grid`. Add `progress` as a list of states.
Add `fairness` as a list of state sets. Each fairness set must occur infinitely
often. The checker finds reachable fair cycles that can avoid progress forever.
It reports their strongly connected components. Finite deadlocks are separate.
No feasible fair cycle gives inconclusive. MCP `formal_model_live` returns the
same report. These are exact finite-graph results. Native RTL liveness-to-safety,
k-liveness and RTL fairness certification remain open.

Additional native qualification on 2026-11-13: rIC3 1.5.2 proved the safe
counter and found its seeded fault. It proved both pinned HWMCC cases in
2.194 s total wall time, including preparation. Engine-only time was 1.904 s.
The build used Rust nightly-2025-11-20 and Homebrew GMP/MPFR. Evidence and binary
hashes are in `/tmp/rvw-deep-ric3-{counters,hwmcc}/result.json`.
This does not establish full-block capacity or a representative comparison.


### Timed event simulation and assertion counts

```sh
rvw formal simulate --verilog dut.sv checks.sv --top dut --events events.json --out sim --backend icarus --check-x
rvw cov merge sim --source-root sim
rvw cov merge case1=sim/coverage.dat --source-root sim
```

The event file uses `rvw.formal-events/1`. It declares `timescale` as `1ns` or
another unit, `clocks` as input port names, and an `events` list. Each event has
an integer `time` and an `inputs` map of exact-width binary strings. Strings can
contain X/Z with Icarus. The first event sets every input at time zero. Later
events can set a subset. Times must increase. Clock changes and data/reset
changes use separate timestamps after initialization. No clock is invented.

The runner samples output observations after all updates at each timestamp.
`--observe PORT` selects outputs. The default selects all outputs. Icarus
preserves four-state values; `--check-x` fails on any observed X/Z, including
startup. Use a declared reset sequence when startup state matters. Verilator
uses two-state simulation and refuses X checks and X/Z input values.

The event file can load a captured register state before replay:

```json
"state": {
  "trace": "capture.fst",
  "time": 125,
  "scope": "testbench.dut",
  "registers": ["left.counter", "right.counter"]
}
```

The trace path is relative to the event file. VCD and FST are accepted.
`time` uses trace timestamp units. The first event row must match every traced
top-level input, including clock levels and reset values. The selected registers
must cover all DUT register bits. The loader checks this against the elaborated
model. It excludes generated property-history registers. A Boolean monitor wire
that aliases DUT state does not remove that state from the coverage check.

This route requires Icarus and complete elaborated flip-flop state. Register paths
can name child instances. Repeated instances have distinct state-bit identities.
The loader reads the RTLIL flip-flop destinations before JSON aliases merge.
A combinational register alias cannot substitute for an actual flip-flop output.
Memory and black-box state remain refused.

The loader lets input setup settle, then forces all recorded register values.
It waits for derived-clock and asynchronous-control events to settle while every
register remains forced. It then releases the registers. This prevents setup
from overwriting loaded four-state values. Clock and control logic can be internal.
Logical event time zero starts at that point. No assertion is checked during
setup. Property histories start empty and count subsequent property events.
Result `state_load` records the trace hash, timestamp, scope, register values and
state-bit count. X checks can observe unknown loaded state and its later removal
by an independent clock or an asynchronous reset. These are finite native
continuation observations. They do not prove reachability or full formal replay.

Both backends replay explicit top-input raw property events: `@(irq)`,
`@(negedge rst)` and event lists such as `@(posedge irq or negedge rst)`.
The event input must be a top-level port. Edge terms must be scalar.
A change event can use a vector. Icarus X/Z edges use the four-state event rules.
Verilator accepts only two-state inputs and does not measure X.

A job with raw events samples all its top-level property clocks before each
input update. It applies one private monitor pulse for each matching property
event, even if several terms fire at the same timestamp. Thus `@(data) data`
checks the old data value. A property that reads another changing clock also
sees its old value. The time-zero row initializes inputs and does not fire raw
monitor events. Output observations still use the settled post-update values.
Result `property_events` records each event and its private monitor clock.

This replay scope requires properties in the top module. It accepts inline
properties and zero-argument named properties. It refuses same-event `disable
iff`, internal/hierarchical events, event expressions and clocking blocks.
Verilator refuses unknown inputs and X checks. General asynchronous formal semantics remain separate.
The [event scheduling reference](https://dvcon-proceedings.org/wp-content/uploads/asynchronous-behaviors-meet-their-match-with-systemverilog-assertions.pdf)
explains why concurrent assertions sample values before an asynchronous event.

Both backends accept Boolean two-clock implication:

```systemverilog
p: assert property (@(posedge source_clk) request |=> @(posedge target_clk) response);
```

`|=>` checks the response at the first strictly later target-clock event.
`|->` permits a target event at the same timestamp as the source event.
Each accepted request retains its obligation. Several requests before the target
event produce separate pass or fail counts. The simulation samples both operands
before the event inputs change. An unknown antecedent does not start an attempt.
An unknown consequent fails an active assertion. Assume and cover forms use the
same event mapping. Counts report activated obligations. They do not count a
false antecedent as a passing attempt.

This subset requires one scalar input edge per clock, a Boolean antecedent and
a Boolean consequent. Either edge can be posedge or negedge. Properties must
belong to the top module. Sequence operands, sampled functions and disable cancellation remain refused.
Zero-argument named properties and module-local aliases are accepted. It is a finite native
simulation route. Formal lowering keeps its cross-clock refusal. C1
`cross_clock_properties` records the clocks, terms, operator and monitor id.
The rules for simultaneous and strictly later events follow IEEE 1800-2017
clause 16.13, [multiclocked properties](https://rfsoc.mit.edu/6S965/_static/F25/documentation/1800-2017.pdf).

Native replay also accepts Boolean `s_eventually`, `until`, `until_with`,
`s_until` and `s_until_with` properties. Both implication forms and zero-argument
named properties are accepted. Each request retains a counted obligation.
A response can fulfill several requests and produces one observation per request.
Until forms can record a finite failure when the hold operand is false.
Inclusive until also tests that operand at the completion sample.

These observations do not replace liveness with a finite deadline. Each property
reports `pending` obligations at the trace end. This includes a final `|=>`
request that has not reached its consequent's first sample. Pending assertions
make C1 inconclusive. Pending assumptions also prevent a fault verdict under an
unverified environment. Recorded finite failures and output X observations retain
their normal priority when the assumptions are resolved. Coverage counts contain
only witnessed completions. Cover obligations can remain pending without hits.

This subset uses the existing clock-local sampled history. It accepts explicit
top-input event clocks and Boolean operands. Unbounded sequence composition,
local captures and cross-clock eventual response remain outside native
unbounded replay. C1 `unbounded_properties` records each property,
operator, event clock and implication form. These are finite native observations.
They are not unbounded proofs or full simulator scheduling qualification.

Native unbounded replay accepts `disable iff` from top-level input controls.
An asserted condition cancels active and delayed requests between property
events. Reports add `cancelled` counts. Cancellation produces neither success
nor failure and does not erase an earlier failed observation. Clock history is
not reset by cancellation.

Disable controls must stay stable at every property event timestamp. They must
not read their own event inputs. Internal expressions and sampled disable calls
remain refused. These limits keep the current disable value separate from the
pre-event values used by the property. Unknown disable values do not cancel.
Finite native monitors also use Boolean-true cancellation, so X/Z disable values
cannot hide a failed check. Four-state cases require Icarus. Formal unbounded
cancellation remains outside the existing engine adapter.

Runtime input updates preserve pre-event sampling on both backends.
The same supported SVA set runs as simulation monitors on either backend. This
includes separate checker files and properties clocked by an asynchronous input.
The runner records assertion pass/fail and cover hit/miss counts per property.
An assumption failure makes the stimulus inconclusive. No assertion samples and
no requested X checks gives `error` with `inconclusive=no_checks`. A finite
simulation pass does not discharge pending future obligations or establish a
proof. Full SystemVerilog simulator scheduling is not qualified.

`result.json` is C1 with counts, event observations and input snapshots. Its
coverage artifact uses the Verilator point-record format for sampled assertion
passes and SVA cover hits. These are monitor observations, not RTL code coverage.
The source is generated `simulation.sv`. Use explicit `name=coverage.dat` inputs
when merging multiple event tests. `formal_simulate` exposes the same runner
through MCP. Native smoke tests cover both simulators, unrelated clocks, async
reset, an asynchronous property input, seeded assertion faults and Icarus X data.
## Bounded bug hunting

Use `rvw formal bug-hunt --manifest PLAN.json --out OUT --budget 60 --timeout 10`.
MCP `formal_bug_hunt` runs the same command. The plan uses pinned engine-race
`top` and `sources`, with a schedule such as:

```json
{"depths": [20, 40, 80], "seeds": [1, 7],
 "engines": ["aiger:rIC3", "abc:bmc3", "smtbmc:yices"]}
```

Combine these fields with the pinned source manifest. The runner freezes source
bytes, increases bounds, varies rIC3 seeds, and runs each other engine once at
each depth. It retains unstarted tasks after a budget stop or concrete failure.
A completed search remains inconclusive. There is no cover-reachability claim.
Use coverage-directed `swarm` priorities for searches from observed states.

The rIC3 1.5 compatibility wrapper translates SBY's older BMC flags. It clears
inherited Python launcher settings from OSS CAD Suite. Native checks at depth
20 with seed 7 returned bounded success on the safe counter and found its fault.
Results: `/tmp/rvw-deep-ric3-bmc-after3-{counter,fault}/result.json`.
The EBMC source build uses a macOS 14 deployment target on Darwin because the
current Xcode C++ library rejects the upstream macOS 10.15 target. This changes
build compatibility only. It does not change the verification source.


### Composite channel payloads and database bindings

Stream intents accept `payloads`, a list of `signal` and `width` entries.
Every field gets its own stability check. Flow intents accept per-field
`signal` and `max_value` entries. A Flow still has no backpressure contract.
The earlier single-payload form remains supported.

```sh
rvw formal properties contracts.json --channels checks.json --db design.db --out channels.sv
```

Database binding resolves channel names to local RTL ports and payload widths.
It uses the recorded clock domain. If the channel signals have no domain id,
set `domain_signal` to a register path in that channel's component. The register
provides a domain anchor; it does not supply a hand-written clock name. A direct
clock/reset connection to a local input port must exist in the database.
Mixed domains, ambiguous clocks, derived control expressions, clock enables,
soft reset, pruned signals and nonlocal channel ports remain refused.
Reset polarity comes from the database. Only rising-edge domains are supported.
Use reviewed `max_values` keyed by payload path for composite Flow bounds.

The generator writes `channels.sv.bindings.json` with `rvw.channel-bindings/1`,
the resolved bindings, captured database identity and database staleness warnings.
This records the supplied database, not physical timing or current RTL parity.
`formal_properties` accepts the same `db` option through MCP.
## EBMC native qualification

EBMC 6.2 was built from `2f4f2fc76f450557de3eef5f3e3d075869999e85`
with CBMC `f17df18eaf4a84e7ab7b4e8f60bac1685ad05045` outside the repository.
The Darwin deployment-target patch described above makes its version report
`dirty`. No verification algorithm was changed. Native positive/fault counter
checks proved the safe case and found the fault. Native AIGER input proved
`a19-p15`; induction on `itc99-b13-p10` was inconclusive at depth 20.
Raw results and executable hashes are in
`/tmp/rvw-deep-ebmc-{counters,hwmcc}/result.json`.

The adapter now passes original AIGER bytes to EBMC's native reader. The top
module field applies to Verilog only. The Yosys preparation translation remains
separate. This avoids assigning Yosys global-clock syntax to EBMC semantics.

Final two-case pinned HWMCC measurement on this host, 2026-11-13. Each job
had a 12 s timeout and depth 20. Wall times include preparation. Solved means
an unbounded proof or a concrete counterexample. Bounded passes are separate.

| Mode | Engine | Solved / 2 | Bounded passes | Total wall time (s) |
|---|---|---:|---:|---:|
| prove | `smtbmc:yices` | 1 | 0 | 2.660 |
| prove | `smtbmc:z3` | 1 | 0 | 2.079 |
| prove | `smtbmc:bitwuzla` | 1 | 0 | 2.387 |
| prove | `smtbmc:cvc5` | 1 | 0 | 2.503 |
| prove | `aiger:suprove` | 0 | 0 | 0.010 |
| prove | `abc:pdr` | 2 | 0 | 1.567 |
| prove | `aiger:avy` | 0 | 0 | 2.302 |
| prove | `aiger:rIC3` | 2 | 0 | 1.977 |
| prove | `ebmc` | 1 | 0 | 0.390 |
| bmc | `smtbmc:yices` | 0 | 2 | 2.237 |
| bmc | `smtbmc:z3` | 0 | 2 | 2.359 |
| bmc | `smtbmc:bitwuzla` | 0 | 2 | 1.789 |
| bmc | `smtbmc:cvc5` | 0 | 2 | 1.773 |
| bmc | `btor:btormc` | 0 | 2 | 1.507 |
| bmc | `abc:bmc3` | 0 | 0 | 1.725 |
| bmc | `btor:pono` | 0 | 2 | 1.792 |
| bmc | `aiger:rIC3` | 0 | 2 | 1.808 |
| bmc | `ebmc` | 0 | 2 | 0.208 |

Raw rows, errors, missing dependencies, hashes and commands:
`/tmp/rvw-deep-final-{prove,bmc}/result.json`. Avy crashed. `suprove` was
absent. ABC BMC3 returned errors on these AIGER imports. Pono and BTORMC
returned bounded passes. This small subset is not a capacity qualification.
No small-open-core property campaign or licensed comparison ran.

Connection tables (#107)
------------------------

`rvw formal connectivity connections.csv --db design.db --out report` reads
project-owned CSV, JSON or TOML declarations. JSON uses a `connection` array.
TOML uses `[[connection]]` rows. CSV uses a header row:

```csv
id,kind,source,destination,condition,delay,inversion
payload,required,io_source,io_destination,io_enable,1,false
```

`condition` aliases `enable`. It names one active-high Boolean signal.
`delay` aliases `latency` in clock cycles. `inversion` selects a bitwise inverse
of the source before delay. The default kind is `required`. The default delay
is zero. `mode` is a second Boolean condition. Both conditions are sampled with
the source. Delayed valid state clears on synchronous active-high reset.

The structural pre-check resolves endpoints in the captured database. The
reverse check walks each declared destination back to declared source and
condition boundaries. It lists other top input influences. Clock, reset and
initialization edges are excluded from this data influence inventory. Missing
endpoints, opaque logic and truncated cones remain incomplete. The reverse
check also inventories every top output. Outputs with no required source
declaration are reported. It does not prove transfer semantics.

Add `--run` for bounded checks. Add `--proof-mode prove --engine smtbmc:yices`
for an unbounded safety proof and a separate bounded activation witness.
The campaign binds captured RTL hashes to the database. Required transfers can
report `contradicted` from a counterexample. Only an unbounded pass with an
activation witness reports a row as `proven`. Forbidden influence uses two DUT
copies with independent initial state. Its failures remain incomplete because
state differences need review. Proofs retain source RTL assumptions. Required internal endpoints can use captured Yosys observation ports.
Internal forbidden influence and inout ports remain unsupported.
The overall report remains incomplete and exits 1. It lists `unproven` and
`contradicted` row IDs. It never grants design acceptance.

MCP tool `formal_connectivity` runs the same command and returns its report.

Internal connectivity observations
---------------------------------

Required connections can observe internal RTL source, destination and condition
signals. The backend flattens captured RTL with Yosys. It resolves the exact
SpinalDB RTL path in the flattened netlist and checks the width. It exposes
observation outputs without cutting or replacing drivers. Top port names,
directions and widths must match the captured database. Unmatched internal
names and widths remain incomplete. The report records original RTL hashes,
the transformed RTL hash, observation bindings and reproducible Yosys scripts.

Both the transfer proof and activation witness use the same transformed RTL.
Top output condition signals can also guard required transfers. Internal
forbidden influence still needs a state-coupling backend and stays incomplete.
The reverse inventory includes all top outputs, including those with no
required source declaration. Source assumptions and the single-clock/reset
restrictions of the native formal flow still apply. No design acceptance is
inferred from these observations.

Forbidden-source activation requires legal variation
--------------------------------------------------

A DUT assumption can force the source input to one value in both copies.
A noninterference proof in that environment cannot witness source variation.
The activation job now samples source inequality with mode and enable, then
delays the combined predicate by the declared latency. A proved safety relation
without this witness remains incomplete. This check does not remove source
assumptions or convert them into unrestricted influence evidence.

Generate an RVFI project (#63)
-----------------------------

`rvw formal rvfi-generate binding.json --out generated` writes `rvw.toml` and
a wrapper template for a core with RVFI output ports. The project-owned JSON
uses schema `rvw.rvfi-binding/1`. It supplies `top`, `clock`, `reset`, `ports`
(the complete RVFI field-to-DUT-port map), `inputs` and `outputs` (auxiliary
DUT port widths), `root` (riscv-formal checkout), `verilog`, `isa`, `nret`,
`checks`, `depth` and `solver`. Optional `defines` and `check_options` retain
the runner format. Paths resolve against the binding file. Environment
variables in paths expand when the generator runs. `name` sets the project name.

Auxiliary inputs are unconstrained. The generator adds no bus assumptions.
Review the generated wrapper for the selected DUT environment. The port map
must cover all RVFI fields. Duplicate DUT ports and invalid widths are errors.
Generation checks the current supported ISA and runner settings. It does not
prove adapter conformance or validate the actual RTL port directions.

Then run `rvw --project generated/rvw.toml formal riscv --out proof`.
The runner generates `checks.cfg`, expands RVFI connections and runs SBY per
requested check. NRET can be 1 to 16. Check channel indices must be below NRET.
The retirement cover requires a witness on every channel. A missing channel
witness makes otherwise passing checks inconclusive. The C3 report retains
per-check results and settings. C4 never accepts a core from bounded evidence.
MCP tools `formal_rvfi_generate` and `formal_riscv` expose these steps.

`examples/vexriscv/formal/binding.json` supplies a VexRiscv RVFI binding for the
upstream riscv-formal example. It has unconstrained bus response and error
inputs. It does not replace the reviewed environment in `wrapper.sv.in`.
The two-channel native fixture tests an independent ADD implementation and a
mutation of channel 1. It establishes generation and channel-check execution,
not conformance of a real core adapter. Real-core trap, killed instruction,
memory lane and multiple-effect observations remain required for #63.
Sail Zicond checks (#64)
-----------------------

`rvw formal sail-zicond --model SAIL_RISCV --compiler sail --out MODELS`
compiles the RV32 CZERO.EQZ and CZERO.NEZ register-result rules. It requires
Sail 0.20.1 and sail-riscv commit
`549e723031b34b5ffea5bbb56367be15c7a38a9e`. The generator checks the SHA-256 of
`model/extensions/Zicond/zicond_insts.sail` before compilation. It extracts the
condition, result selection and R-type encoding from that file. It lowers
32-bit `zeros()` to a zero literal. It lowers inequality to negated equality
before compilation. This avoids an unspecialized runtime bitvector helper.
Generated SystemVerilog logic is retained without logic rewrites.

The manifest records source lines, expressions, encoding matches, compiler and
library hashes, compiler options and generated file hashes. It identifies the
actual compiler result port. An explicit RVFI shell adds decode, register
addresses, x0 suppression, PC advance and zero memory effects. Those shell
assignments are not a compilation of the full Sail machine. The extension is
enabled. Illegal-instruction behavior when it is disabled is excluded. RV64,
CSR MISA and privileged behavior are excluded. Other widths are refused by RTL
elaboration. No complete architectural conformance claim is made.

Add the generated files through the existing project `instruction_models`:

```toml
[riscv_formal.instruction_models]
czero_eqz = "models/insn_czero_eqz.v"
czero_nez = "models/insn_czero_nez.v"
```

Request `insn_czero_eqz_ch0`, `insn_czero_nez_ch0` and `cover` in `checks`.
Use the supported upstream base ISA in `isa`. When an instruction model is new,
the runner adds it to the private copy of that base ISA instruction list. It
records `instruction_set_additions`. It changes no upstream source file. Each
new model needs an explicitly requested check. These additional checks do not
claim that the upstream base ISA includes the extension.

The independent native fixture checks all operand and instruction bits. It
checks result selection, encoding, register fields, x0, PC and memory effects.
Result, decode and PC mutations must fail. A separate campaign runs both new
models through upstream riscv-formal against a correct and a faulty RVFI unit.
MCP tool `formal_sail_zicond` exposes generation.
Custom instruction interfaces (#122, #169, #155)
----------------------------------------------

`rvw formal custom-isa examples/custom-isa/xadd.json --out generated` reads a
versioned core-owned interface. `rvw.custom-isa/1` supports XLEN 32 or 64 and
pure R-type instructions in custom opcode spaces 0, 1, 2 and 3. Each instruction
declares its encoding, operands, extra state, effects and result expression.
Extra state must be empty. Memory and trap effects must be `none`. PC behavior
must be `next`. Unknown effects and incomplete semantics are errors. A repeated
encoding is an error. Standard opcode spaces are refused.

A result is `rs1`, `rs2`, an unsigned XLEN constant or a tree such as
`["add", "rs1", "rs2"]`. Supported operations are add, sub, xor, and, or, sll
and srl. Results wrap to XLEN. Shifts use the low log2(XLEN) shift bits.

Exports include a stable `interface.json`, pure Verilog result modules, GNU
assembler macros, GNU C inline functions, a standalone Python disassembler,
and a GCC RISC-V machine-description fragment. The GCC fragment needs manual
backend integration and a toolchain build. It is not an installed plugin.
GCC and binutils use GPL-3.0-or-later. The standalone decoder is generated
project code. No objdump plugin is installed. Native tests compile GNU hooks
and assembly for RV32I/ILP32 and RV64I/LP64. They check the compiled instruction
and register operands. They do not run a custom instruction on a DUT.

`plan.json` contains operand boundary bins, vectors and dependency cases.
`tests.S` tests those vectors, destination/source aliases, equal sources and
x0 discard. It returns zero for success and one for failure. Generated expected
values share the declared semantics. Project `reference_vectors` provide
independent expected values. Project `mutants` provide alternate result trees.
The report checks reference vectors and requires every supplied mutant to be
detected. Missing independent inputs and surviving mutants remain explicit gaps.
A mismatching independent vector gives exit 1. Generation otherwise gives
exit 0, which is not a DUT pass. Extra state, memory, custom exceptions and
runtime trap/calling-convention qualification remain outside this subset.
MCP tool `formal_custom_isa` exposes the same generator.
Pinned profile obligations (#104, #80, #141)
-------------------------------------------

`rvw formal profiles plan.json --out report` imports named RVA23/RVB23 extension
obligations from hash-pinned profile AsciiDoc files. It handles user and supervisor
profiles separately. Supervisor profiles inherit unprivileged mandatory and
selected optional extensions. Inherited mandatory requirements cannot become
optional. Optional extension obligations activate when the ISA manifest selects
the extension. The full captured bullet text retains its normative conditions.

The project-owned `rvw.profile-plan/1` file supplies `isa_manifest`, `profiles`
and `documents` (path and SHA-256). `examples/profiles/profiles.example.json`
pins two documents at riscv-profiles commit
`e030b70992447784ad9081045d47ce6e278f381e`. Set `RISCV_PROFILES` to that checkout
and `RVW_ISA_MANIFEST` to the project's existing `rvw.isa/1` file. Paths can use
these environment variables. The report also runs the existing ISA consumer
configuration check for compiler, DUT, reference, ACT and coverage probes.
Missing probes and unknown versions remain inconclusive.

Each profile lists `implemented`, `verified`, `missing`, `unsupported` and
`not_selected` IDs. Implemented means declared in project data. `unsupported`
can list obligation IDs or extension names. A `proofs` entry needs `result`,
its `sha256` and the exact `obligation_sha256`. Verified requires a matching
unbounded formal pass, at least one assertion and a reachable environment.
The mapping of the obligation to the proved property requires review. Captured
proof restrictions remain visible. A bounded pass cannot mark an item verified.

`tests` and `checkers` map obligation IDs to project test paths and checker IDs.
The report records existing test hashes and missing test files. Empty test lists
are missing evidence. Add `--baseline old-plan.json` to list added, removed and
changed obligation text or selection, affected checkers and missing tests.
Changes require explicit adoption. The command changes no source pin or model.

Scope is the named-extension inventory. Base/endian/ECALL paragraphs, notes,
recommendations and implicit extension dependencies are not expanded. Conditions
inside an obligation are retained as text for its reviewed proof mapping.
This report never grants full profile compliance. It always exits 3 for a valid
report. MCP tool `formal_profiles` returns the same result.
### Equivalence counterexample replay

`rvw formal cex --result EQUIV_RUN --out REPLAY --emit-testbench` also accepts
`rvw.formal.equiv/1` results with status `not_equivalent`. The selected witness
must belong to a failed native eqy partition. The command captures that
partition's exact RTLIL model and both source snapshots. It uses the existing
Yosys simulation, waveform editing, reduction and testbench export paths.

`source_flow: "equiv"` marks these reports. A `reproduced` disposition requires
an observed failing assertion in the baseline simulation and the same assertion
in the edited simulation, with no assumption failure. The result remains
`inconclusive` as proof evidence. Exit 1 retains the existing replay contract.
Generated testbench files are not a separate reproduction result.

The replay targets the failed closed output partition. Its input names come
from the captured miter, such as `__pi_a`. It does not map a witness into a
project simulator or claim a whole-core reproduction. Source files are retained
for inspection. Missing models or a nonfailed partition are refused.


### Pinned solver rechecks

`rvw formal recheck --result FAILED_RUN --pin bad=0 --out RECHECK`
runs a bounded solver check over the captured RTLIL model. Repeat `--pin` for
more signals. A pin uses an exact net name in the captured top module and an
integer value. Pins can refer to inputs or internal nets exposed by that model.
Each pin adds an equality assumption at every formal sample. The original
drivers, state, assertions and assumptions remain in the captured model.

The command first checks that the pinned model can reach the full requested
depth. An inconsistent pin is `inconclusive`. A passing recheck is bounded and
conditional on the original restrictions plus all pins. It does not establish
that a source change fixes the design or authorize a coverage exclusion.
`--depth` defaults to the original BMC depth. The minimum depth is two samples.
The output retains both SBY jobs, their logs, the pinned model and captured
inputs. The `formal_recheck` MCP tool has the same inputs. Native tests check a
removed failure, a retained failure and an assumption conflict with Yosys/SBY/Z3.
### Shortest solver counterexample

`rvw formal shortest --result RUN --max-depth 20 --out DIR` checks increasing
sample depths in a captured BMC model. The model must have exactly one assertion.
The first FAIL is shortest only if all smaller depths passed. An unknown or
failed solver invocation stops the search as inconclusive. Reaching the depth
limit with PASS results also stays inconclusive. This is not an unbounded proof.
The original assumptions and restrictions remain. Each SBY job and trace is
retained. `formal_shortest` provides the same operation through MCP.

When counterexample replay uses `--pdg`, successful SpinalTrace output also
writes `explanation.json`. The agent-readable chain lists source locations,
observed values, timestamps and dependencies. It keeps the dynamic graph's
accuracy status. Missing accuracy is incomplete. The chain is observed trace
evidence. It does not prove counterfactual causality or a source repair.
### Explicit blackbox model contracts

`formal equiv --blackbox-contract contract.json` can add trusted behavioral
models to both RTL revisions. Unresolved blackboxes remain refused. The manifest
uses paths relative to itself:

```json
{"schema":"rvw.equiv-blackbox/1", "models":["Primitive.v"],
 "obligations":["The physical Primitive implements this behavioral model."]}
```

A model can replace a declared Verilog blackbox. It cannot use RTL assumptions
or nondeterministic cells. The existing state and clock restrictions still apply.
Both proof snapshots capture every model source. The result retains model and
manifest hashes and the explicit unresolved obligations.

A completed modeled run has `status: "conditional"` and `contract_verdict` of
`equivalent` or `not_equivalent`. It always exits 1. Missing proof evidence stays
`inconclusive`. The command proves behavior only under the supplied models.
It does not prove those models against a physical blackbox or an independent
implementation. No conditional result can grant unconditional equivalence.
`formal_equiv` exposes the same source inputs, revision exports, state hints and
blackbox contract. It returns conditional evidence without granting a pass.

### Sail binary bit-manipulation rules

`rvw formal sail-bitmanip --model SAIL_RISCV --compiler SAIL --out OUT`
compiles pinned Sail RV32 result rules for 19 binary instructions. MCP tool
`formal_sail_bitmanip` uses the same generator. The subset contains Zba
`sh1add/sh2add/sh3add`, Zbb `andn/orn/xnor/min/max/minu/maxu/rol/ror`, Zbs
`bclr/bext/binv/bset`, and Zbc `clmul/clmulh/clmulr`.

The generator extracts result expressions and encodings from sail-riscv commit
`549e723031b34b5ffea5bbb56367be15c7a38a9e`. It checks each source hash. It also
checks the hashes of the arithmetic and prelude helpers. Sail 0.20.1 compiles
these expressions. The manifest records source text, encodings, helper hashes,
compiler identity, compiler library hashes and generated file hashes.

This is a binary result slice. It assumes that the selected extension is enabled.
The RVFI shell supplies register fields, x0 suppression, PC advance and empty
memory effects. Immediate instructions, unary instructions, RV64, floating-point
state, CSR effects and privileged transitions are not generated. These limits
remain open under #64. No generated model establishes a core proof by itself.

### Architectural state without RVFI

`rvw formal state-generate state.json --out OUT` generates a private formal
project for a core without RVFI. MCP tool `formal_state_generate` uses the same
operation. Run the project with `rvw --project OUT/rvw.toml formal riscv`.

The project-owned JSON uses schema `rvw.architectural-state/1`. Declare `xlen`
as 32 or 64, the DUT `top`, `clock`, `reset`, and its `verilog` file list. Declare
`riscv_formal` settings with `root`, `isa`, `nret=1`, `checks`, `depth`, `solver`
and optional per-check options. Paths are relative to the state map. Source
files must be self-contained SystemVerilog files.

The `signals` object maps each observation below to a distinct named RTL wire.
Hierarchical paths use dots. The generator flattens the design and exposes
observations as output ports. It does not cut their drivers.

| Observation | Width | Meaning |
| --- | --- | --- |
| `retire` | 1 | One architectural retirement at this edge |
| `insn` | 32 | Retired instruction |
| `pc_before`, `pc_after` | XLEN | PC across that retirement |
| `regs_before`, `regs_after` | 32 * XLEN | Complete register snapshots, x0 in the low word |
| `rs1`, `rs2`, `rd` | 5 | Architectural read and write indices; unused indices are zero |
| `trap`, `intr` | 1 | Retirement trap and interrupt observations |
| `mode` | 2 | Architectural privilege mode |
| `mem_addr`, `mem_rdata`, `mem_wdata` | XLEN | Retirement-aligned memory observation |
| `mem_rmask`, `mem_wmask` | XLEN / 8 | Byte masks; zero for no memory access |

An optional `csrs` name list adds `csr_NAME_before` and `csr_NAME_after` mappings,
each XLEN bits wide. These snapshots are exposed in the wrapper. No CSR
instruction semantics are inferred from their names.

The monitor reads source values from the pre-state and destination values from
the post-state. It checks x0 and unchanged registers outside the selected write.
It generates retirement order from the observed events. It records input hashes,
derived RTL hashes and a no-proof generation status. A project must review
snapshot alignment, instruction indices, bus pairing and fairness. This first
kit does not infer speculative retirement, multiple retirement lanes, CSR
semantics, or independent order conformance. Its native ADD fixtures are not
core conformance evidence.

Native result checks use independent bitvector formulas and wrong-result
mutations. The Zbc checks restrict the multiplier to zero or one selected basis
bit. They keep the other operand arbitrary. Full arbitrary-operand Zbc oracle
comparisons timed out within the short native budget. The basis results do not
discharge those comparisons. Generated instruction models contain no basis
restriction. The RV32 lowering expands the pinned rotate helpers and carryless
loops. It replaces inequality with negated equality, fixes zero widths, and
replaces temporary-concatenation slices with equivalent sized casts for Yosys.
### Sampled generated-clock equivalence

`formal equiv --sampled-events --unmatched-state prove` can compare generated
clocks and simple level-sensitive clock-gating latches. Both complete wrappers
are lowered with Yosys `clk2fflogic` before eqy partitions are built. State stays
inside closed output cones. No state-equality cutpoints are added.

Repeat `--stable-at-edge INPUT` to require that a data input has the same value
on the samples immediately before and at a root-clock rising edge. For example,
use `--stable-at-edge en --stable-at-edge a` for a clock-gating enable and data
input. Each assumption appears in the captured wrapper and `event_model` record.
These constraints do not fix input values or impose a clock frequency.

The model observes one global input sample per formal step. It does not model
multiple transitions between samples, analog glitches, setup/hold margins or
physical clock-tree behavior. Reset and settle count root-clock edges. Stalls
are allowed. Yosys `clk2fflogic` defines the sampled cell update semantics.

A completed sampled-event run reports `conditional` with `contract_verdict`.
It always exits 1. It cannot grant unconditional hardware equivalence.
A conditional counterexample can use the existing `formal cex` simulation path. The
`formal_equiv` MCP tool exposes both options. Advisory dsec is refused in this
mode. Asynchronous state controls remain refused. Default equivalence and other
formal commands keep their existing latch and generated-clock rejection.
### Output latency and mapping

`formal equiv` accepts `--latency-map q=2 --latency-map flags=0`.
A positive value delays the reference output. A negative value delays the candidate.
Each value must be in -64..64. The common startup interval includes the largest
absolute delay. `--output-map q=result` binds a changed output name. All outputs
remain obligations. eqy builds separate closed output partitions. Every partition
must pass with no internal crossbits before the result can be `equivalent`.
`--unmatched-state prove` permits state encoding changes. It does not assume a
state relation. The solver must prove the relation through the outputs.
MCP tool `formal_equiv` exposes the same controls and source revision export.
Blackboxes, memory mappings and generated clocks remain unsupported.

## Uninterpreted arithmetic proofs

Run `rvw formal uf-prove --manifest PLAN.json --out OUT --timeout 12`.
The `formal_uf_prove` MCP tool runs the same job. The manifest uses the pinned
`sources` and `top` fields from `engine-race`. Choose SMTBMC engines with
`engines`, such as `["smtbmc:yices", "smtbmc:cvc5"]`. Add `--cross-check` to
retain all answers. The optional `operators` list selects `bvmul`, `bvudiv`
and `bvsdiv`. An empty list runs the original arithmetic.

The command replaces each selected SMT operator with one global uninterpreted
function per operand width. Equal operands have equal results across states
and properties. Concrete arithmetic is one permitted interpretation. An
unbounded pass therefore proves the original safety property. A failure with
a replaced operation stays inconclusive. Run again with `operators: []` to
check the concrete arithmetic. Source assumptions keep a pass inconclusive
until their activation is checked.

The typed transformation preserves Yosys witness and assertion metadata. It
uses operand widths before extraction, named bit-vector sorts and explicit
`QF_AUFBV` logic. Unknown widths stop the transformation. The report records
source hashes, transformed SMT hashes, operation counts and wrapper identity.
It makes no arithmetic speed claim.

Native smoke checks on macOS ARM64, 2026-11-13: Yices, Z3, cvc5 and Bitwuzla
each proved a registered multiplier pipeline with two replaced operations.
A signed-division pipeline also proved. A division identity was inconclusive
with UFs and proved with concrete arithmetic. A faulty pipeline was
inconclusive with UFs and failed with concrete arithmetic. Each stage used
a 12 s timeout. These are small-design checks, not capacity measurements.

## Native fair AIGER liveness

Run `rvw formal aiger-live --manifest PLAN.json --out OUT --method l2s`.
The `formal_aiger_live` MCP tool uses the same plan. The plan contains `path`
and `sha256` for a self-contained ASCII `.aag` input. The adapter accepts one
bad justice group. Each justice member and fairness literal must recur
infinitely on a violating execution. Ordinary outputs, safety properties and
multiple justice groups are refused. This command does not translate SVA.

`--method l2s` retains all source state and invariant constraints. It guesses
a loop start, saves the complete state and checks a nonempty return path that
visits every justice and fairness condition. Native rIC3 IC3 proves or refutes
the resulting safety property. An accepting cycle is a liveness failure.
`--method k-live --k 4` counts complete rounds through all goals. An unbounded
safety proof is sufficient for liveness. Reaching the selected count stays
inconclusive because a finite accepting prefix can reach it.

Before a proof with invariant constraints or fairness can pass, a separate
exact reduction must find a fair infinite execution. Impossible or unchecked
fairness stays inconclusive. Native stdout, stderr, commands, tool hashes,
reduced model hashes and timings remain in the output directory. Certificates
are not independently validated.

`--method rlive` invokes rIC3's experimental native liveness engine. On pinned
rIC3 revision `02c12ff1407b3474b7eb85c4531a06ad2eb86933`, all five reference
cases failed on its internal unsupported `--no-ic3-pred-prop` option. They
report errors and remain inconclusive. The source build was not changed.

Native macOS ARM64 checks on 2026-11-13 used 12 s stage timeouts. Exact L2S
proved toggling progress and fair input progress. It found accepting cycles
for stuck progress and input progress with no fairness. K-liveness at `k=4`
proved the two good cases and kept the two reached bounds inconclusive. Both
methods kept impossible fairness inconclusive. Results are under
`/tmp/deep-aiger-native4/`. These small models do not establish RTL capacity.

## PDR invariant libraries

Run `rvw formal ic3-lemmas --manifest PLAN.json --out EXPORT --timeout 12`
to export ABC PDR invariant cubes. The manifest uses the pinned `top` and
`sources` fields from `engine-race`. The command maps cubes to named RTL bits.
It skips auxiliary SBY state and unmapped or inverted latches. Mapped cubes
are candidates. A separate unbounded proof checks their conjunction on the
flattened source with the original properties removed. Only a pass writes
`EXPORT/library.json`. Source assumptions are refused.

Run `rvw formal ic3-lemmas --manifest NEW_PLAN.json --library EXPORT/library.json
--out REUSE` to select cached predicates for related properties or revisions.
The `formal_ic3_lemmas` MCP tool exposes both forms. `engines` in the new plan
selects the fresh target portfolio, with SMTBMC/Yices as the default.

Each library entry contains its literals and a complete transition-cone hash.
The cone includes next-state inputs, clocks, reset/enable controls, cell
parameters and initial values. Numeric wire ids and generated cell names do
not define the identity. Unrelated logic can change without a cache miss.
A changed dependency rejects that entry. Unknown drivers, unnamed state,
memories and nonzero-based or ascending signal ranges are not reusable.

Helpers remain assertions. They are never added as assumptions. The target
always needs a fresh native proof. If a job with cached helpers fails, the
report stays inconclusive because the failure can come from the target or
a damaged library. A job with no selected helpers can report the original
target's failure. No proof-time reduction is claimed.

Native macOS ARM64 checks on 2026-11-13 exported and separately proved one
invariant of a modulo-three counter. The entry matched a related property
and a revision with an unrelated output counter. A faulty transition changed
the cone, excluded the entry, and failed the fresh target proof. A source
assumption was refused. Each stage used a 12 s timeout. Raw results are under
`/tmp/deep-ic3-native-tests/`. This is small-design reuse evidence.
# Sail FP, CSR and privileged entry slices

`rvw formal sail-state --model SAIL_RISCV --compiler SAIL --out DIR` compiles
18 kernels from hash-pinned Sail rules. MCP tool: `formal_sail_state`.
Use Sail 0.20.1 and sail-riscv commit
`549e723031b34b5ffea5bbb56367be15c7a38a9e`.

The generated SystemVerilog includes a typed result module and a checker.
Connect the checker to decoded operands and the observed result in a project
wrapper. `valid` must identify the selected retired operation. FP checkers also
check the instruction encoding. No core binding or core proof is implied.

| Kernels | Inputs | Output |
| --- | --- | --- |
| FSGNJ/FSGNJN/FSGNJX, H/S/D | Decoded 16/32/64-bit FP operands `a,b` | Raw FP result bits |
| CSRRW/CSRRS/CSRRC write value | `a` is the CSR read value; `b` is the source value | Proposed 32-bit CSR write value |
| CSRRW/CSRRS/CSRRC access | Low five bits of `a` are rd; low five bits of `b` are rs1 index or immediate | Bit 1 is read; bit 0 is write |
| MRET/SRET/WFI entry | Control fields below | Two-bit entry decision |

CSR immediate forms use a zero-extended immediate as the source value. An rs1
register that holds zero still causes a write when its index is not zero.
The proposed CSR write value applies only when the generated write intent is
set. Projects must check both signals. Supply the CSR read-modify-write value,
which can differ from the destination value for `mip` and `sip`.

Privileged inputs use `a[2:0]` for privilege: U=0, S=1, M=3, VU=4, VS=5.
Other privilege codes disable the checker. `a[3]` is TSR. `a[4]` is VTSR.
`a[5]` is TW. `a[6]` is the platform user-mode WFI option. `b[0]` is the
extension return-privilege check. `b[1]` says S is enabled. Decisions are
0 for allowed entry, 1 for illegal instruction, 2 for virtual instruction,
and 3 for extension return-privilege failure. WFI allowed entry means entry
to the wait state. It does not mean eventual completion.

These exports need no SoftFloat library. FP register zero is writable.
NaN payload and sign bits are preserved by the sign rules. Inputs are after
register unboxing. Arithmetic, rounding, flags, register boxing, CSR legality,
WARL effects, CSR destination values, return-state updates, return targets,
and WFI timeout/wakeup are excluded. FCLASS calls a model/compiler helper
outside this extracted slice. No arithmetic or full-machine proof is claimed.
The manifest records source hashes, exact source text and lines, lowerings,
compiler/library identities, excluded effects and generated hashes.


## Exhaustive RTL initial-value splitting

Run `rvw formal initial-split --manifest PLAN.json --out OUT --timeout 10`.
MCP `formal_initial_split` runs the same operation. The plan uses pinned
engine-race `top` and `sources`, plus `split_variable` and optional `max_cases`.
The variable is a flattened Yosys net name. The default case limit is 16.
A wider variable needs an explicit limit, up to 256 cases.

The runner exports one proof problem for every bit pattern of the variable at
the initial state. It retains the full transition relation in every problem.
The variable can change freely after initialization. `plan.json` records the
complete decomposition and hashes. Every case must prove unbounded before the
original design earns a pass. Existing source assumptions keep it inconclusive.
A subset of successful cases cannot earn success. This is not a time-invariant
input restriction or a state-space abstraction.

Native two-bit reference tests cover all four initial values. The matching
counter pair proved in all four cases. The seeded mismatch produced a concrete
counterexample. Evidence: `/tmp/deep-initial-split2-{safe,fault}/result.json`.
No full-core or capacity result is implied.


## Lazy RAM word refinement

Run `rvw formal lazy-ram --manifest PLAN.json --out OUT --budget 60 --timeout 10`.
MCP `formal_lazy_ram` exposes the same command. A plan contains pinned `top`
and `sources`, a collected Yosys `memory` cell name, optional `engines` and
`depth`, and optional `max_words` with a default of 64 and maximum of 4096.

The runner first uses Yosys `memory_map -formal`. This keeps the source's read,
write, initialization and collision logic. It replaces untracked word state
with unconstrained per-step inputs. Tracked words keep their original drivers.
Abstract failures restore a word, with priority for read addresses seen in the
counterexample and constant read addresses. Missing address samples use a
simple next-word fallback. This affects search order only. An abstract failure
cannot become a design failure. A concrete failure requires all word state to
be restored. Original source assumptions remain unqualified.

Limits: lowering must retain distinct word names and one whole-word flip-flop
driver per word. Aliased words and negative offsets are rejected. The lowering
still contains the original combinational memory logic. Tracked RAM state bits
are not total design-state bits. No general runtime or capacity gain is claimed.

Native evidence on the 16-word, 8-bit reference RAM: an abstract failure restored
address 3. The next unbounded proof passed with 8 concrete RAM state bits from
an original 128. A seeded fault remained inconclusive through all abstract
rounds. It became a concrete failure only after all 16 words were restored.
Evidence: `/tmp/deep-lazy-ram-{proof,fault-proof}/result.json`. A separate native
masked-write test proved after restoring its one addressed word. Five targeted
tests cover driver preservation, initialization removal, aliases and selection.

## Pinned PicoRV32 property-set measurement

`examples/formal/deep/picorv32.json` pins upstream source revision
`ef203c2b0a3fb793280f5114941416c425c5b461`. Fetch it outside the repository
with `scripts/fetch-formal-bench.py`. The default FORMAL export has 23
assertions and two source restrictions: reset sequencing and memory response.
Every problem result stays inconclusive because activation is unmeasured.
The native engine answers below are conditional on those source restrictions.
Each job had a 12 s timeout. Wall time includes preparation.

| Engine | Native answer | Problem result | Wall time (s) |
|---|---|---|---:|
| `abc:pdr` | pass | inconclusive | 10.763 |
| `aiger:rIC3` | pass | inconclusive | 7.808 |
| `smtbmc:yices` | inconclusive | inconclusive | 4.269 |
| `ebmc` | error | inconclusive | 0.506 |

EBMC receives explicit FORMAL and YOSYS defines, matching the formal read.
It rejects this source because `$initstate` is unsupported. The previous
no-properties result exposed the missing FORMAL define and is retained in
the first run. A regression now checks a failing FORMAL branch. No source
restriction was removed or replaced. This is a property-bundle measurement,
not a whole-core qualification. Raw results:
`/tmp/rvw-deep-picorv32-proof/result.json` and
`/tmp/rvw-deep-picorv32-ebmc-formal/result.json`.

## Counter quotient certificates

Run `rvw formal counter-quotient --manifest PLAN.json --out OUT --timeout 15`.
MCP `formal_counter_quotient` runs the same command. The plan declares pinned
Verilog `sources`, concrete `top`, `width`, and smaller `keep_bits`. The default
port names are `clk`, `reset`, `enable`, and `count`. A `ports` object can map
`clock`, `reset`, `enable`, and `count` to other names. All four ports must have
the declared directions and widths. Extra ports are refused. `reset_active`
can be `high` or `low`.

The runner generates `abstract.sv`, an enabled modulo counter of `keep_bits`
width. It proves the relation `abstract_count = concrete_count mod 2**keep_bits`
against the concrete RTL through the existing guarded unbounded flow. A pass
certifies that relation under the recorded initial-reset and clock policy.
It covers projected low bits only. It does not replace a parent design or
certify properties of discarded upper bits. Source environment assumptions
keep the certificate inconclusive. A failed obligation leaves the candidate
uncertified. It does not by itself identify a DUT bug.

The certificate records source, manifest and model hashes, restrictions and the
retained native proof. A changed source needs a new proof. The proof resets the
leaf once at startup, then holds reset inactive. It does not certify arbitrary
future reset sequences. A concrete counter whose enabled increment is two
refutes the candidate that increments by one.

Native reference evidence: the 32-bit counter proved against the 4-bit model.
The increment-by-two candidate failed its obligation. Native tests also check
16-bit to 3-bit projection with an active-low reset and renamed ports. Evidence:
`/tmp/deep-counter-{safe,bad}/result.json`. No full-core result is implied.

## Cover-directed bounded search

Run `rvw formal cover-hunt --manifest PLAN.json --out OUT --budget 60` to
search hard-to-reach covers. The plan uses pinned `top` and `sources`, plus
the `depths`, `engines` and rIC3 `seeds` fields from `bug-hunt`. Optional
`targets` selects unique elaborated cover cell names. Without it, the command
searches every cover. The `formal_cover_hunt` MCP tool runs the same campaign.

Yosys prepares the source with `prep -flatten`, `async2sync` and
`chformal -lower`. Each target becomes a separate negated safety check with
its original enable. Original safety assertions and other covers are removed
from that target job. Source assumptions and all transition logic remain.
The bounded campaign increases depth and varies engines and rIC3 seeds.
The remaining budget is shared over remaining targets.

A concrete failure of the generated check is a `bounded_reachability` cover
hit. The report uses `covered`, never safety `pass`. Bounded success, missing
engines, errors and budget expiry stay inconclusive. They cannot establish
unreachability. The report retains elaborated and transformer hashes, target
source locations, each attempt and native witness paths. No reset or physical
clock qualification is added. Liveness constraints are refused.

Native macOS ARM64 checks on 2026-11-13 used SMTBMC/Yices and rIC3 BMC.
A four-bit counter's value-12 cover was not reached at depth 4 and was reached
at depth 20. Its impossible value-16 cover stayed inconclusive. A deliberately
failing source assertion did not count as a hit. rIC3 used seeds 0 and 1 at
the shallow bound. Both native tests passed in 5.99 s with 6 s stage timeouts.
Results are under `/tmp/deep-cover-native4/`. No capacity improvement is claimed.
The AXI slow tests run independent good traces and seeded bad traces through
SBY in prove mode. They use Yices for AXI4 and ABC PDR for AXI4-Lite. Each
expected fault must return FAIL. Tool errors do not count as detected faults.
These small fixtures prove monitor behavior, not a connected design.

### Exact TileLink bus types

SpinalChecks reports the qualified TileLink bus type, enabled live signals
and library options in its `buses` inventory. Use
`rvw formal buses --db design.db --type-report design.checks.json --out OUT`
when SpinalDB records only the ambiguous class name `Bus`. Binding requires
one exact top, component path and live signal-name set match. Missing and
duplicate matches remain unsupported. The report does not prove that two
elaborations have equal behavior. Use matching project captures.
MCP `formal_buses` accepts `type_report`. Project bus entries accept the same
key as a path relative to `checks.generate.json`.

### TileLink transaction trackers

Complete bus fields enable `protocol_profile=tilelink-uh-probe-c`. The generator
checks A/D sources, request/response kinds, sizes, masks, parameters and
multibeat headers. It supports Get, Put, ArithmeticData, LogicalData and Hint.
Coherent channels add Acquire/Grant, Release/ReleaseAck, GrantAck sinks and
Probe/ProbeAck tracking. Different addresses can share a probe source.
`--depth` limits pending probe pairs. Capacity failures are instrumentation
limits. Missing fields retain named `unbound_checks` reasons. Zero-bit source
and sink fields use the exact options from `--type-report`.
Coherent B is restricted to probes. The trackers do not infer negotiated
address ranges or operation capabilities. They do not check cache permissions,
independent memory data or forward progress. Generation is not a proof run.
The slow SBY tests require exact PASS/FAIL results on independent good and
seeded bad fixtures, including reset with pending transactions.

## Installer flags and refreshed native measurements

Select `--with-ric3`, `--with-ebmc`, `--with-pono`, `--with-avy`,
`--with-suprove`, `--with-bitwuzla`, `--with-cvc5` or `--with-yices` with
`scripts/install.sh`. rIC3 and EBMC build in the external native engine cache.
The other flags reuse an executable already on PATH or fetch checksum-pinned
OSS CAD Suite 2026-10-22 under `~/.cache/rvw/formal-engines`. A requested engine
missing from that platform bundle is an error. Presence does not qualify it.
The flags publish selected backend launchers in the external native engine
cache. The generated `env.sh` includes that launcher directory. Pono also
enables its `btorsim` trace dependency.

On this macOS ARM64 host, the rIC3/EBMC installer flags and their `--check`
completed on 2026-11-13. The Pono, Avy, Bitwuzla, cvc5 and Yices flags and checks
also completed with the installed native tools. The development environment
was restored with the locked dev and MCP extras after installation.

The refreshed harness used the externally installed checksum-pinned suite.
It ran the pinned HWMCC subset and PicoRV32 manifests
in `examples/formal/deep`. Each native stage had a 12 s timeout at nice
priority. Times below include preparation and sum over each case. They are
a new measurement, not a paired speed comparison with earlier tables.

HWMCC subset: two preprocessed cases. Only conclusive problem results count
as solved. Bounded passes cannot count as unbounded proofs.

| Engine | Prove solved / 2 | Prove total (s) | Bounded passes / 2 | BMC total (s) |
|---|---:|---:|---:|---:|
| `smtbmc:yices` | 1 | 3.632 | 2 | 1.301 |
| `smtbmc:z3` | 1 | 1.706 | 2 | 1.178 |
| `smtbmc:bitwuzla` | 1 | 1.748 | 2 | 1.411 |
| `smtbmc:cvc5` | 1 | 1.692 | 2 | 1.247 |
| `aiger:suprove` | 0 | 0.007 | N/A | N/A |
| `abc:pdr` | 2 | 0.887 | N/A | N/A |
| `aiger:avy` | 0 | 1.272 | N/A | N/A |
| `aiger:rIC3` | 2 | 1.143 | 2 | 2.222 |
| `ebmc` | 1 | 0.166 | 2 | 0.356 |
| `btor:btormc` | N/A | N/A | 2 | 1.442 |
| `abc:bmc3` | N/A | N/A | 0 | 1.884 |
| `btor:pono` | N/A | N/A | 2 | 2.807 |

Avy errored on both HWMCC cases. ABC BMC3 also errored on these two cases.
The SMT prove jobs and EBMC each left one case inconclusive. Raw reports:
`/tmp/deep-pinned-refresh-hwmcc-small-{prove,bmc}/result.json`.

PicoRV32: one upstream property set. Its source assumptions remain unchecked.
The native PDR and rIC3 passes are conditional observations. Every qualified
solved count is zero. EBMC errors on unsupported `$initstate`.

| Engine | Prove observation | Qualified solved / 1 | Prove total (s) | BMC observation | BMC total (s) |
|---|---|---:|---:|---|---:|
| `smtbmc:yices` | inconclusive | 0 | 8.661 | bounded_pass | 3.627 |
| `smtbmc:z3` | timeout | 0 | 12.607 | timeout | 12.451 |
| `smtbmc:bitwuzla` | timeout | 0 | 12.392 | bounded_pass | 2.793 |
| `smtbmc:cvc5` | timeout | 0 | 12.289 | timeout | 12.280 |
| `aiger:suprove` | not_installed | 0 | 0.003 | N/A | N/A |
| `abc:pdr` | conditional_pass | 0 | 3.003 | N/A | N/A |
| `aiger:avy` | error | 0 | 1.494 | N/A | N/A |
| `aiger:rIC3` | conditional_pass | 0 | 2.439 | bounded_pass | 3.694 |
| `ebmc` | error | 0 | 0.281 | error | 0.274 |
| `btor:btormc` | N/A | N/A | N/A | bounded_pass | 5.607 |
| `abc:bmc3` | N/A | N/A | N/A | bounded_pass | 2.065 |
| `btor:pono` | N/A | N/A | N/A | bounded_pass | 1.769 |

Raw reports: `/tmp/deep-pinned-refresh-picorv32-{prove,bmc}/result.json`. These
small cases do not establish full-block capacity, commercial parity or
whole-core correctness. Missing engines and unsupported modes are not passes.

The checksum-verified darwin-arm64 archive has no `suprove` executable. The
installation attempt failed explicitly and retained the 501 MiB archive in
the external cache. Its absence is not a qualified proof-engine result.

Native adapter checks with the earlier suite: 18 passed. With the pinned
suite: 17 passed, 1 failed. The failure was
`test_counter_quotient.py::test_native_reset_qualified_relation_and_refuted_candidate`.
SBY returned PASS, but Yosys 0.70 wrote interned `$pub@...` module names and
a `twines` name table in `design_prep.il`. The shared runner's assertion counter
did not resolve the top and reported an error. The counter certificate stayed
inconclusive. The runner needs this format support before that command can
qualify with this suite. Its earlier Yosys 0.64 native result remains separate.
Raw checks: `/tmp/deep-{final,pinned}-native/`.

### Free-list partition checks

`formal template freelist_conservation` adds a free-bit partition to the
existing independent allocation-pool model. `free_bits` and `live` must be
disjoint and cover exactly `USABLE`. Accepted allocation/release events update
expected live ownership. `INITIAL_LIVE` and `USABLE` are literal project
parameters. The project microarchitecture document can bind this rule, ROB
count conservation and the other resource templates by named signals. See
`rvw/src/rvw/checks/README.md` for port names. This does not infer flush or
rename-recovery semantics.

### AXI response precedence

RVALID requires an AR accepted on an earlier edge. BVALID requires AW
and the complete W packet accepted on earlier edges. A current-edge
handshake does not authorize a response on that edge. The generated
AXI4/AXI4-Lite trackers and native Spinal AXI4 trackers enforce this order.
W can still arrive before AW. Reset clears pending transaction state.
A later response to discarded state is an orphan.
See the read/write dependency rules in
[Arm IHI 0022H](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/IHI0022H_amba_axi_protocol_spec.pdf).

### Flush and forwarding age variants

`fifo_flush` adds explicit flush priority to the FIFO-order template. It
discards both queued data and current-edge events.
`store_forward_age` uses a project `older_than` matrix to choose the youngest
eligible store. It supports circular slot layouts. The existing `store_forward`
variant retains its declared higher-index-is-younger contract. Both variants
require a unique forwarding source and compare the selected data unit. Use
per-byte instances for byte merging. An inconsistent age relation cannot
silently remove every candidate. The separate `age_matrix` rule checks the
full active relation. All variants bind through project data and the existing
`formal template` CLI/MCP interfaces.

## Generated bus environment

An RVFI binding can declare `bus_environment` entries. The supported protocol is
`stream-response`: ready/valid commands and ordered response pulses. Each entry
binds one-bit output `valid`, input `ready`, input `response`, optional output
`write`, `service_bound` (1..64) and `max_pending` (1..64, default 8).
Writes do not need responses in this protocol. Use another environment for buses
that acknowledge writes. The interface follows the ready/valid handshake in the
simple bus protocol templates. Those safety templates alone do not imply fairness.

The generated assumptions limit command stalls and the time between responses
while reads are pending. They prohibit unsolicited and zero-cycle responses.
They do not constrain request data, instruction data, retirement or traps.
Outstanding requests must stay within `max_pending`; an assertion checks this
instrumentation limit. It is not an assumption about the core.
`environment_constants` can constrain declared input ports, for example bus error
inputs. These are explicit environment restrictions. They are not ISA rules.
Both declarations are recorded in `rvfi-generation/1` output. Remove them to
retain the unconstrained wrapper. A passing finite liveness check remains bounded
and applies only to the recorded environment.
### Prepared RTLIL name compatibility

The shared assertion counter accepts escaped hierarchy names from older Yosys
and public interned names from Yosys 0.70. It resolves `leaf` and `suffix`
entries in the `twines` table. Missing name entries cannot qualify a pass.
The pinned-suite counter relation and seeded bad increment both passed their
expected-outcome tests on 2026-11-13: six targeted tests passed in 6.99 s.

### Native backend failure classes

The pinned macOS ARM64 Avy crashes with SIGSEGV on the two HWMCC problems
whose folded AIG has zero latches. It also crashes on the PicoRV32 bundle
with 23 outputs. Portfolio error rows now retain the exact AIG dimensions and
these observed input classes. These observations do not identify the internal
Avy fault or establish support for other AIG shapes. Errors remain errors.

The pinned rIC3 1.5.2 `rlive` path calls its own removed
`--no-ic3-pred-prop` option. This is an internal CLI incompatibility on the
native justice input path. Its result records `unsupported_backend_cli`.
Use `l2s` or `k-live` for the existing checked reductions. No fallback result
is substituted. The pinned darwin-arm64 suite has no suprove executable.
Its portfolio status remains `not_installed`.

### Exact PicoRV32 proof conditions

Portfolio and engine-bench results retain the elaborated assumption predicates,
enables, model hash and exact source excerpts. The pinned PicoRV32 conditions
are `restrict property (|last_mem_nowait || mem_ready || !mem_valid)` and
`restrict property (resetn != $initstate)`. On each rising edge,
`last_mem_nowait` shifts in `mem_ready || !mem_valid`. Thus the memory condition
requires progress now or in its four recorded samples. The initial history is
unconstrained. Reset is low in the initial state and high in every later state.
The result stays inconclusive because assumption activation is not checked.
A native pass proves the bundled assertions under these exact restrictions.
It does not prove the restrictions or remove them from the design.

## Unbounded RVFI instruction portfolio

`rvw formal riscv-proof --project PROJECT --checks insn_add_ch0,insn_and_ch0
--out OUT --engines abc:pdr,smtbmc:yices --timeout 180` captures the upstream
`mode prove` instruction checkers. The generated testbench enables
`RISCV_FORMAL_UNBOUNDED`, so the check input is arbitrary instead of selecting
one fixed BMC cycle. This command supports instruction checks only. It preserves
source reset assumptions and project bus assumptions. Optional upstream
`RISCV_FORMAL_ASSUME` blocks are refused.

Each captured, self-contained source has a SHA-256 hash and an engine-race
manifest. The command reuses the native engine portfolio. Each engine has the
specified time limit. Jobs run in sequence, with the engines of one job in
parallel. Select at most three engines for the native campaign limit.
MCP tool `formal_riscv_proof` has the same arguments.

`capture.json` records source identity and the captured jobs. `result.json`
records each portfolio result, including engine rows. Unbounded engine success
is distinct from bounded success. A portfolio with source assumptions remains
inconclusive under the portfolio activation policy. The command exits 1 for a portfolio failure. Otherwise it exits 3 and does
not grant ISA signoff. Run retirement cover with `formal riscv`
separately. The capture itself does not establish adapter conformance.
### Finite-memory equivalence

`formal equiv --memory-map --unmatched-state prove` lowers finite RAMs to registers
with Yosys `memory_map -formal`. Use this when one implementation uses RAM and
the other uses explicit register words. It retains RTL read/write and initial
value semantics. It adds no storage equality assumptions. Each RAM word remains
part of a closed output cone. This can increase solver cost substantially.

Use `--latency-map read_data=1` for a candidate with one additional fixed read
cycle. This compares the delayed reference observation. It does not infer a
transaction protocol or ignore invalid payload values. Do not apply a global
latency shift to a write acknowledgement unless that signal also moves.

The result records `memory_mapping` for both sides. `state_bits` counts all
mapped register Q bits, including non-memory state. Array and temporary net names
receive legal inventory aliases. Their bit connections and initialization
attributes remain intact. The default still refuses memories. Native controls
prove a four-word RAM against registers with zero and one read cycle of lag.
A changed data bit produces a counterexample. These controls do not prove a
cache, a memory macro or automatic internal cut-point matching.
### Compiled property portfolios

Engine-race and engine-bench accept pinned `format: "rtlil"` sources. Each
source uses `read_rtlil` directly. No Verilog export/reparse is required.
EBMC reports `unsupported_input` for this source class. Native races use at
most three engine workers.

`compiled_variants.build` retains compiled assumptions and makes conservative
cell-output cuts for RAM, all adders, or flip-flops. RAM cuts free all memory
outputs. Adder cuts are broader than counter quotient abstraction. They do
not certify a reduced counter. State cuts can expose spurious failures.
Use these variant answers only as abstraction observations. A transformed
failure cannot establish a DUT failure. No automatic refinement is added.

The 2026-11-13 VexRiscv capacity table and exact limits are in
`examples/formal/deep/vexriscv-capacity.md`. All 43 compiled safety problems
remain unsolved. RAM, adder, UF and state-cut attempts earned no qualified gain.
The table lists missing property classes and witness-reconstruction failures.

## ISA kit signoff table

Use the [retained timeout replay](timeout-rerun.md) for a later 30-minute
comparison on an idle machine. It selects the prior timeout checks, preserves
their captured model and writes the engine, time, depth and load table.
The idle-machine capacity table is NOT yet measured.

Timeout rows now show elapsed seconds, the time limit, the starting host load
and the next setting to try. Native engine rows retain the ending load too.
Use `--timeout 1800` for a 30-minute retry at the same depth. A high-load
timeout stays unresolved. It does not establish a real capacity limit.
The current default remains 110 seconds. Check depths stay in project data.
Long low-load measurements are required before either default can change.

`rvw formal isa --project PROJECT --out OUT --timeout 110` runs all selected
bounded instruction and consistency checks. It prints one row per check and
writes `rvw.isa-signoff/1` to `OUT/result.json`. Use `--unbounded` to run the
instruction proof portfolio after the bounded checks. `--engines` selects up
to three proof engines. MCP tool `formal_isa` returns the same report.

Outcomes are `proven`, `bounded` with its cycle bound, `failed`, `unsupported`,
`not applicable`, or `inconclusive`. Timeout and missing reachability evidence
are inconclusive. Machine checks without bindings and adapter equivalence
remain explicit gaps. Generated instruction models in the project run through
the same instruction checker. The command does not infer their provenance.
Exit 1 means a check failed. Exit 3 means that full ISA signoff is incomplete.
Use a new output directory for each run. The native trees retain exact source
hashes, assumptions and individual cycle settings.
Autocheck input errors return exit 2 and `rvw.autocheck-error/1` JSON.
Declare clock and reset as one-bit input ports in the manifest. Invalid
bindings do not produce a proof result.
## Automatic strategy plans

Run `rvw formal strategy --model design.json --history bench.json --out plan.json`.
MCP: `formal_strategy`. Supply a Yosys `write_json` model and optional repeated
engine-bench history files. The planner counts state bits, memory cells,
adders, multiplication/division and liveness cells. Boolean safety starts with
PDR/rIC3. Memory or arithmetic puts word-level engines first. Qualified history
orders engines by solved count, then mean wall time per solve. Conditional and
bounded observations cannot train the order. The recorded VexRiscv table has
zero qualified solves and therefore cannot supply a learned winner.

The plan selects RAM, UF, bound counter-leaf or state-cut candidates from these
features. It requires a liveness reduction when live/fair cells exist. It runs
no proof and changes no RTL. State size is a cell inventory, not reachable
state. Counter leaf bindings still need a project declaration. Supplied history
need not predict a different design. No ML package is used.

## Machine transition properties

`rvw formal machine-checks --manifest MAP.json --out OUT --run` generates
RV32 properties and runs a bounded assertion job and a reachability job per
rule. Omit `--run` to generate only. MCP: `formal_machine_checks`.
`rvw formal isa --machine MAP.json` runs these checks with the instruction kit.

The map has schema `rvw.machine-checks/1`, `xlen = 32`, `sources`, `top`,
`clock`, `reset`, `depth` and `checks`. Each selected rule maps every named
monitor input to a local RTL identifier under `signals`. The generator inserts
an instance in a captured source copy. It never edits the external source.
`machine_checks.RULES` defines each input and its width. Source widths must
match those inputs. Use `not_applicable` with a reason for absent features.
Use `unsupported` with a reason when a feature lacks observations.

The rules check x0 operand and destination values, a killed retirement slot,
exception entry, interrupt entry with direct or vectored targets, trap return,
CSR read/write state, instruction memory and the PC chain. Entry and return
inputs must represent the two states of one architectural transition. Return
checks cover PC, interrupt enable and restored mode. They do not cover all
WARL rules, delegation, or previous-mode clearing. `trap_pc_chain.redirect`
and `redirect_pc` must describe any entry or return since the last retirement.
`flush_retirement.retired_killed` must track the retiring instruction, not a
current flush pulse for an unrelated instruction.

CSR selection adds `csr` and `write_mask`. The catalog supplies address,
privilege and read-only state. `op` is 1 for replace, 2 for set and 3 for
clear. A zero operand suppresses set/clear writes. `before`, `after` and
`read_data` are aligned storage observations. Project masks cover ordinary
storage only. Dynamic WARL, aliases and autonomous updates need another model.
Instruction memory uses an arbitrary immutable aligned 32-bit word. It checks
that a retirement at that address has the assumed fetch value. It excludes
compressed and self-modifying code. Project data must pair each fetch address
with its returned data. These transition slices do not prove a complete
privileged machine.

Both native tasks must pass to earn `bounded N`. A timeout or unreachable
trigger is inconclusive. The reset assumption asserts reset only in the
initial state. Results retain captured source hashes and all native trees.
## Re-proof timing across revisions

Run `rvw formal revision-bench --base base.json --revised revised.json --out OUT`.
MCP: `formal_revision_bench`. Both files use pinned engine-race source manifests.
The runner exports a certified PDR library from the base, then alternates fresh
proofs of the revised target with and without cone-matched helper assertions.
The default is three trials per path. The report gives signed median time saved
and the separate one-time export cost. Helpers remain assertions. Changed
cones cannot select old predicates. No cached proof verdict is returned.

The checked-in `examples/formal/deep/revision` sample adds an unrelated output
counter. All six native target proofs passed and each reuse trial selected one
matching lemma. Cold median: 1.623 s. Reuse median: 1.801 s. Time saved:
-0.178 s. Library export cost: 4.906 s. Thus this sample shows no time gain.
The eight-second native stage limit and nice priority apply to this local run.
These small-counter timings do not establish core-scale reuse performance.

## Live proof-progress events

Engine-race writes `progress.jsonl` while installed engines run. Engine-bench
jobs retain the same file under each problem directory. The result's
`progress_events` field names the stream. A dashboard can tail this JSONL file.
Each started, sample and finished event contains the manifest property ID,
engine, local sequence number, elapsed seconds and sampled process-group RSS.
Samples run once per second. Missing memory or depth is `null`.

Depth is the largest solver step seen in the native log. It means the solver
started that step. It does not mean the bound passed. PDR frames have a separate
field and cannot be read as unrolled depth. Requested depth is never copied into
the observed field. Final native status is an engine observation. Source
conditions and cross-engine disagreement still control the problem verdict.
The property ID identifies the manifest problem, which can contain a bundle
of assertions. This is not per-assertion progress inside one bundled engine.

### Active-low reset and halt in state maps

Architectural-state maps can set `reset_active_low = true`. The formal wrapper
then drives the core reset with `~reset`. Add a `halt` signal to observe a core's
halt state. Older maps retain the constant-zero halt output. These options do
not change the trap rule: a trapping instruction has no destination write, and
the register frame must stay unchanged. The PicoRV32 example has measured
simulation comparisons and a retained bounded equivalence failure. See
`examples/picorv32/formal/README.md` before using that map for signoff.

`rvw formal sva-lower` returns exit 2 and structured `status: unsupported`
for unsupported source constructs. Preprocess macro-bearing RTL first. Input
or output file errors return `status: error`. Neither result writes lowered RTL.

For constant-value ASYNC-reset FFs, `bmc`, `apps` and `autocheck` accept
`--event-model --async-reset`. The event model samples clock and reset events.
Default single-clock flows refuse ASYNC state and give a configuration fix hint.
Use one project elaboration entry if a SYNC reset implementation is selected.
Rebuild the database after changing that entry.
### Datapath binding kit

Use `rvw formal datapath --unit mul --db design.db --out proposal` to find
arithmetic candidates and propose port bindings. No proof runs. Each candidate
requires designer confirmation. See [the kit guide](README-datapath-kit.md).

### Internal state partition proofs

`rvw formal equiv-partitions` matches register boundaries automatically and
proves each observation in its full state cone. It keeps output equivalence and
internal-relation results separate. No internal cut equality is assumed.
See [the partition guide](README-equiv-partitions.md).
### Real-core Scala DSL campaign and regression reuse

The [VexRiscv campaign](../../../../examples/vexriscv/README.md#scala-dsl-property-campaign)
compiles project-owned DSL assertions into a native Verilator ISA harness.
It prepares one SBY BMC task per assertion for `formal regress`. Its measured
table states each simulation and formal result. The campaign measures finite antecedent matches and bounded cover witnesses.
Instruction-identity liveness remains unimplemented.

Use `formal regress --proof-cache DIR` to reuse exact self-contained engine
observations. The MCP argument is `proof_cache`. A C3 `cache.hit` preserves the
original conditional result and bound. It does not establish non-vacuity.
Only restricted self-contained Verilog jobs qualify. Read the
[cache contract](../../../../docs/contracts/formal.md#exact-regression-observation-cache)
for the input closure and artifact checks.
## Sail RV32 M checks

`rvw formal sail-m --model MODEL --compiler SAIL --out MODELS` compiles all eight
RV32 multiply, divide and remainder expressions. MCP tool `formal_sail_m`
returns the generation manifest. The model and helper files are pinned by hash.
The compiler is Sail 0.20.1. Select these models with
`riscv_formal.instruction_models`. Keep `RISCV_FORMAL_ALTOPS` disabled.

The rules retain Sail signedness, zero-divisor results and signed overflow.
The generated shell supplies the R-type decode and RVFI wiring. Packed aggregate
syntax and signedness casts have bit-preserving Yosys lowerings. Sail's
`quot_round_zero` and `rem_round_zero` externs have explicit signed 128-bit
SystemVerilog `/` and `%` bindings. These primitives are part of the trusted
compiler boundary. The manifest records the final model hashes and lowerings.
It does not claim full Sail-machine translation or extension-disabled traps.

The ISA front command now runs an activation cover for each instruction at its
assertion cycle. A successful native cover needs a trace. A timeout or missing
trace makes the instruction row inconclusive. General retirement cover alone
cannot qualify these rows. Each activation job retains the original reset and
bus assumptions. Consistency checks retain their separate retirement cover.

See `examples/vexriscv/formal/SAIL_M.md` for the RV32IM profile, corner tests and
native campaign. Preparation and simulation results are separate from proof.

### Antecedent reachability and DSL source lines

Finite temporal simulation reports `activated` separately from `passed`.
Each matched antecedent increments `activated` at its own endpoint. Thus a
passing implication can have zero observed activations. This is finite evidence.
Other monitor routes report null when activation is not measured.

A `formal regress` row can add `activation_sby = "response-cover.sby"`.
Use one cover-mode job that checks the antecedent, with the assertion job's
engine. Optional `activation_task` selects its SBY task. The runner checks the
one-cover inventory and records reached, not reached within the bound, timeout
or error. It does not infer unreachable antecedents from a bounded miss.

The Scala builder writes source-line comments. The temporal frontend retains
these as `source` in property reports and C1. A generated regression manifest
can retain the same `source` field for C3 failure attribution. The VexRiscv
campaign supplies both activation jobs and locations. A wrapper around the DSL
can use `sourceDepth = 1` to attribute the statement to its caller.

### Module-local property defaults

The temporal frontend accepts a simple module-local default clocking block:

```systemverilog
default clocking cb @(posedge clk); endclocking
default disable iff (reset);
response: assert property (request |=> acknowledge);
```

It expands the defaults to explicit controls before finite lowering or named
property expansion. An explicit clock overrides the default clock. An explicit
`disable iff` overrides the default disable. Named aliases receive the controls
at their resolved definition. Defaults do not cross module boundaries.

This subset accepts one empty inline default clocking block and one default
disable declaration per module. Clocking skews, clocking IO declarations,
separate named clocking selection, nested defaults and duplicate defaults remain
refused. Each engine retains its existing event and reset limits. In particular,
formal unbounded reset cancellation, general nested unbounded composition and
full multi-clock proof remain unsupported. These defaults do not change that
scope. The generated support table records paired native finite cases.
## Conditional instruction abstraction

`rvw formal riscv-abstract --project PROJECT --manifest MAP.json --checks
insn_add_ch0,insn_and_ch0,insn_lui_ch0 --out OUT --timeout 180 --budget 400`
captures the upstream unbounded checkers. MCP tool `formal_riscv_abstract`
returns the same report. The manifest has schema `rvw.riscv-abstraction/1`.
It declares the core module, clock, reset, one-bit `in_flight` observations,
collected `memory` name and proof `engines`. `--engines` can override the engine
selection. Project signal names stay in the manifest.

The generator adds an assumption that at most one tracked stage is active.
The project must name every relevant stage. Fetch queues are not inferred.
This is a conditional restriction, not a proven pipeline invariant. The code
reuses the shared `lazy_ram` word abstraction. It preserves source reset and
bus assumptions. The concrete restricted source also gets a bounded instruction
cover. This cover does not certify every source assumption.

The legacy Verilog export can leave internal `$initstate` and `$anyseq` cell
instances that its reader cannot resolve. The command retains the cut JSON
netlist and retries through RTLIL. It changes the representation, not the formal
cells or assumptions. A failed cut model needs refinement. It does not reject
the core. A conditional native proof remains separate from full ISA signoff.
The top-level report stays inconclusive unless a concrete failure is established.

The RAM phase has a budget per check. Concrete cover has a separate time limit
of at most 60 seconds. Native proof jobs each have the selected timeout. At
most three engines can run for one portfolio. Checks run in sequence through
the CLI. The measured three-case experiment used one engine per case and three
cases in parallel under the private core lock.

`formal_riscv_proof` also now returns exit-3 inconclusive results through MCP.
Its earlier shared adapter treated that valid outcome as a tool error.

`keep_words` can retain selected concrete RAM words in the RTLIL retry. This
uses their real state, writes and initial values. It adds no correctness
assumption. The VexRiscv example retains word zero after an abstract
counterexample corrupted the x0 storage. The other 31 words remain free inputs.

`formal isa --abstraction MAP.json` runs these conditional experiments after
the bounded instruction kit. A closed native abstraction proof gets its own
row and scope. It does not change the full instruction row to proven.

The ISA table also lists unselected instructions from the declared upstream
ISA list and missing consistency checks for each retirement channel. They are
unsupported gaps. A short project check list cannot silently qualify the rest
of its declared ISA.

### Executed literal resource scenarios

`formal scenario-compile` and MCP `formal_scenario_compile` emit an RV32 MMIO
program and a CPU-backed pyuvm virtual sequence from resource-aware plans.
Generation does not execute them. The
[scenario guide](SCENARIOS.md#literal-mmio-execution-sources) states the supported
literal operations. The linked composed VexRiscv example ran both native
consumers and compared the same 12 observed MMIO values per consumer.

### Nested eventual milestones

The liveness frontend accepts `req |-> s_eventually (a && s_eventually b)`.
It also accepts further nested milestones, up to eight Boolean terms. A later
milestone can hold at the same sample as the prior milestone. Every request
must complete the ordered chain. New requests cannot discharge older requests
before their own milestones occur. A separate obligation set prevents new
requests from blocking acceptance after older requests complete.

The emitted acceptance signal must hold infinitely often. No finite deadline
replaces eventual completion. The native corpus compares periodic traces with
an independent existential oracle. It also runs positive and negative
liveness-to-safety jobs. This is a subset of nested composition. Nested until,
unbounded sequence concatenation, disjunction of temporal operands, formal
reset cancellation and multi-clock proof remain unsupported.

### Mine candidates from simulation samples

`rvw formal trace-mine --manifest signals.json --trace samples.jsonl --out OUT`
checks finite samples and emits `MinedProperties.scala`. Repeat `--trace` for
separate programs. The manifest declares `signals` as unsigned widths and can
add `onehot_sets`. Each JSONL row supplies an integer for every declared signal.
Use separate traces at reset boundaries. Missing, unknown and out-of-width
values are errors.

The miner checks Boolean implications, guarded next-sample stability, mutex
pairs and declared one-hot-or-zero sets. It drops any candidate refuted by a
supplied sample. `--minimum` sets the minimum activation count. Set candidates
also need observations of every member. The default is two observations.
Output rows remain candidates. Review them and use a fresh formal job before
claiming an invariant. The emitted properties are assertions, not assumptions.
See the [measured VexRiscv run](../../../../examples/vexriscv/mining-results.md).

## Dynamic IMSIC indirect CSR oracle

`rvw.formal.csr_aia_indirect.ImsicIndirectModel` supplies a bounded independent
reference for selector-dependent IMSIC registers. It supports RV32/RV64 EIP
and EIE words, eidelivery, legal eithreshold values, separate M/S files, and
VS routing to a supplied guest file. It follows the register layout and
unspecified reset state in the [AIA IMSIC specification](https://docs.riscv.org/reference/aia/v1.0/IMSIC.html).
It does not materialize dynamic aliases as independent static catalog CSRs.

Call `select(context, value)`, `write(context, data, guest=0)` and
`read(context, guest=0)`. Call `msi(file, identity)` at accepted delivery to the
interrupt file, not at issue of a possibly delayed bus store. The returned
expectation has a value and known mask. Its `compare` method returns match,
mismatch or inconclusive. Initial implemented bits are unknown. Reserved bits
are zero in this declared subset. Unsupported selections remain model gaps.

Eleven unit cases cover selector routing, guest-file changes, pending-bit
updates, unknown initial state, RV64 words, bounds and non-power-of-two identity
capacity. No core binding, CSR denial test, delivery timing proof, APLIC model,
major-priority model or complete AIA qualification was run.
### Prove Boolean two-clock implications

`rvw formal cross-prove --source model.sv --top TOP --out OUT --mode prove`
checks one Boolean two-clock implication with `|->` or `|=>`. Each property
clock must be a distinct scalar top-level input. Posedge and negedge events
are accepted. Source must be preprocessed. Other assertions and assumptions
need separate jobs. Sampled functions, reset cancellation and temporal
consequents remain unsupported in this path.

This path uses `multiclock on` and Yosys `clk2fflogic`. Both property clock
inputs start low. Each global step can change inputs. The property samples settled values
from before that step's transition. The nearest eligible target event completes
all outstanding requests. An overlapped implication includes requests born at
a simultaneous target edge. A nonoverlapped implication retains those requests
for the next target edge. No bound replaces that next-event rule.

No clock fairness is assumed. A target clock that stops can leave pending
requests. The property is a safety check at eligible target events, not a
liveness claim that they occur. A separate cover job checks one reached
obligation. Its witness does not prove universal activation or clock fairness.
C3 and JUnit come from the existing regression runner. BMC observations keep
their bound. Induction observations are conditional proofs in this discrete
model. No event between global samples, full SystemVerilog scheduling, analog
clock behavior or metastability is modeled.

For a zero-latency byte-addressed RAM interface, declare
`[riscv_formal.memory]` and add `@MEMORY_ENVIRONMENT@` to the wrapper.
See the ISA combinational RAM environment in `docs/contracts/formal.md`.
Use full transfer masks with the upstream byte-addressed instruction models.
An aligned RVFI adapter needs the corresponding checker configuration.
Do not constrain DUT addresses to hide an adapter mismatch.

Split integer datapath jobs with `--operand-prefix-bits N --operand-prefix K`.
This fixes the high N bits of `b`. Enumerate K from zero through `2**N-1` to
cover the full operand domain. Each result names its exact interval. A subset
of passing partitions is a partial proof. For a specific divisor in a 16-bit
unit, use N=16 and K equal to that divisor. Check every remaining divisor
before claiming a whole-unit proof.
