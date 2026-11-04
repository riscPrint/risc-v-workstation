# SpinalChecks

Assertions generated from an elaborated Spinal design, and the flows that use them: simulation
monitors, SymbiYosys BMC from reset, BMC from a simulation state, and X-propagation.

Commercial counterparts: JasperGold Superlint / FXP and VC Formal AutoChecks / FXP (checks derived from
the design), Jasper state swarm and VC Formal sim-based init (start a proof from a simulation state).
TODO FV items 5 and 7. Generic for any Spinal design; BOOM is one user (`boom/`).

| Path | What |
|---|---|
| `src/main/scala/spinalchecks/` | The library: `SpinalChecks.install` (the phase), config, report, `ChecksSim` (simulation read-back) |
| `src/main/scala/spinalchecks/demo/` | Demo designs with planted bugs (`ChecksDemo`, `DeepBugDemo`) and `GenDemo` |
| `src/test/scala/` | Verilator tests: every planted bug fires its check and only it |
| `scripts/demo.sh` | Everything on the demos, end to end (no BOOM, no lock) |
| `scripts/make-j4.sh` | `SPINAL_MAKE_CMD` wrapper capping SpinalSim's Verilator `make -j` |
| `boom/` | BOOM adapter: separate sbt build over the spinal-boom clone (`BoomChecks`), `waivers.txt` |
| `../rvw/src/rvw/formal/` | `rvw formal bmc | from-sim | xprop` (Python CLI, uses yosys/sby) |

## Checks

A Spinal phase, inserted after naming and before the IO/hierarchy checks, walks every component of the
elaborated design and adds:

| Kind | Where | Fails when |
|---|---|---|
| `stream.valid_hold` | every `Stream` port and selected internal stream, except a producer fully covered by consumer checks | `valid` dropped while stalled (`valid && !ready` the cycle before) |
| `stream.payload_stable` | same streams (driven payload signals only) | payload changed while stalled |
| `mem.index` | every port of a `Mem` whose size is not a power of two | enabled port with `address >= wordCount` |
| `vec.index` | every dynamic read of a non-power-of-two `Vec` (Spinal `Multiplexer`), one per index signal | `index >= size` |
| `enum.legal`, `fsm.state_legal` | enum registers whose encoding has unused codes (StateMachine state registers get `fsm.`) | value is not a declared state |
| `progress.watchdog` | opt-in: `ProgressSpec(name, signalRegex, maxCycles)` | no progress for `maxCycles` cycles (Bools: any high; one wider signal: value changed) |
| `tilelink.burst_stable` | channels of a Spinal `tilelink.Bus` with multi-beat messages | inside a burst (after its first beat was accepted): a header field (opcode, param, size, source, address, ...) differs from the first beat's, or a stalled beat's payload changed. Before the first beat is accepted the message may change (rocket-chip's TLArbiter does; its TLMonitor allows it) |

| `tilelink.request_legal`, `tilelink.response_legal` | TileLink A/D | illegal opcode, parameter, size, alignment, mask or corrupt flag |
| `tilelink.source_busy`, `tilelink.response_match` | TileLink A/D | source reuse or response without a matching request opcode and size |
| `tilelink.release_busy`, `tilelink.release_match` | TileLink C/D | Release source reuse or unmatched ReleaseAck |
| `tilelink.sink_busy`, `tilelink.sink_match` | TileLink D/E | Grant sink reuse or unmatched GrantAck |
| `axi4.address_legal` | AXI4 address channels | illegal size, burst, boundary or exclusive address options |
| `axi4.read_match`, `axi4.read_capacity` | AXI4 AR/R with a declared limit | unmatched ID, wrong last beat, illegal EXOKAY or issuing overflow |
| `axi4.write_match`, `axi4.write_beats`, `axi4.write_capacity` | AXI4 AW/W/B with a declared limit | unmatched B, wrong W length, illegal EXOKAY or queue overflow |

All checks are inactive while the component's reset is active. `mem.index`, `vec.index` and `enum`
checks on a register without a reset value are armed once the register is first written (an
assignment of it executes), so every written value is checked, the first included, and the power-up
value of a register that is never written is not (it is X in hardware; `rvw formal xprop` covers it). Stream rules on the toplevel's slave
(input) streams describe the environment: in a formal config (`SpinalConfig.includeFormal`) they become
`assume`. A producer can use consumer checks only when the phase proves a full direct connection
of `valid`, `ready` and every payload field. This applies to internal streams feeding child slaves
and child masters feeding parent streams or sibling slaves. All required consumer checks must be
enabled and unwaived. A wrapper chain must end at retained checks. Otherwise both streams keep
their checks. A child master consumed only through its fields keeps its own checks.

Each check has a stable id `<kind>:<instance path>.<object>` (e.g. `stream.valid_hold:fifo.io_push`),
the Scala source line of the checked object (with `SpinalChecks.withLocations`), and a named fail
signal `chk_<kind>_<object>` in the Verilog. Ids are taken when the checks are inserted, before Spinal
allocates final names, so they use identity paths fixed at that point (`SpinalChecks.instanceIds`):
a named component's segment is its name, an unnamed one (created inside a loop body) gets its class
name with a lower-case first letter, and siblings that would share a segment get `_1`, `_2`, ... in
child order (named children first). Objects without a name (`stream`, `mem`, `state`, `index`) or with
a repeated name get the same suffixes within their component. Each id therefore names exactly one
check, and a repeated id stops elaboration with an error. The report's `path`, signal names and the
run report's `fail_signal` use the final Verilog instance name, which can differ from the id
(`branchDecode_1` in the id, `branchDecode_4` in the Verilog; `wrap` can become `wrap_1` when a
definition `Wrap` holds the name). No path segment is empty.

Selection: `ChecksConfig(enable = globs, disable = globs, waivers = Seq(Waiver(glob, reason)))`, a
waiver file (`<glob> <reason>` per line; prefer exact ids, as `boom/waivers.txt` does), or environment variables (`SPINALCHECKS_MODE`, `_ENABLE`,
`_DISABLE`, `_WAIVERS`, `_STREAMS`, `_PROGRESS=name=regex@cycles`). Globs match ids; `*` crosses dots. Waived and
disabled checks are not inserted, but the report lists them with the reason.

Modes:

- `assert` (default): Spinal `assert` (severity ERROR). The Verilog has `assert(!chk_...)` under
  `ifdef FORMAL` (SymbiYosys) and a `$display` otherwise (Verilator keeps running).
- `monitor`: simulation bookkeeping instead of asserts: sticky `fired`, a firing count, the first firing
  cycle (all `simPublic`), and a `$display` of the first 3 firings. `ChecksSim.firings(dut)` reads them.
- `both`.

`ChecksSim.firings`, `runReport` and `writeRunReport` require `monitor` or `both` mode.
They refuse reports when an inserted check has no monitor state. A report with firing checks
changes a caller's `status: pass` to `status: fail`.

## Use

```scala
import spinalchecks._
val (cfg, checks) = SpinalChecks.install(SpinalConfig(targetDirectory = "gen"),
  ChecksConfig(mode = Mode.Monitor, progress = Seq(ProgressSpec("retire", """io_retire_\d+_valid""", 10000))))
val located = SpinalChecks.withLocations(cfg)(new MyTop)   // optional: source lines (elaborates twice)
SimConfig.withConfig(located).withVerilator.compile(new MyTop).doSim { dut =>
  ...
  ChecksSim.writeRunReport(dut, "run-checks.json")       // rvw.checks-run/1: fired checks, counts, first cycle
}
// gen/MyTop.checks.json (or ChecksConfig.reportPath): rvw.checks/1, every check with id, status,
// source, module and fail signal, plus every Stream/Flow (valid/ready/payload names) for xprop.
```

For formal, elaborate with `SpinalConfig(...).includeFormal` and `Mode.Assert`, then:

```sh
rvw formal bmc      --verilog gen/MyTop.v --top MyTop --checks gen/MyTop.checks.json --depth 20 --out out/bmc
rvw formal xprop    --verilog gen/MyTop.v --top MyTop --checks gen/MyTop.checks.json --outputs --payload --out out/x
rvw formal from-sim --verilog gen/MyTop.v --top MyTop --trace wave.fst --cycle 7680 --depth 30 \
                    --checks gen/MyTop.checks.json --out out/fs
```

Every command writes `result.json` (`rvw.formal/1`) and prints failures by check id and Scala line.

What a result means:

- `status`: `pass`, `fail`, `unknown`, `error`, `timeout`, or `no_checks` (the proven design has no
  assertion: nothing was checked). `assertions` is the number of `$assert` cells in the design sby
  proved (`sby/model/design_prep.il`, counted per instance). Exit code 0 only for `pass`; 1 for every
  other status (result written); 2 for an input error (no result).
- A run owns its `--out` directory. It takes an exclusive `flock` on `<out>/.rvw-formal.lock` before
  it removes or writes anything there, and holds it until it ends. A second run on the same directory
  (another process, or a nested call) stops with exit 2 and changes nothing. Use one `--out` per
  concurrent run.
- After the lock, the run deletes the previous `result.json` first. A failed run never leaves an old one.
  The MCP tools (`formal_bmc`, `formal_from_sim`, `formal_xprop`) return a result only if it parses and
  its status agrees with the exit code. Otherwise they return an error with the log tail.
- Before sby starts, the run removes the earlier `sby/` directory and the earlier Yosys outputs
  (`state.il`, `module_ports.il`, `targets.json`). `pass` needs sby's exit code 0 and the same `rc=0`
  in its log. `result.json` records both as `solver` (`exit`, `log_rc`).
- Depths that cannot check anything after the reset are rejected: `bmc` needs `--depth >= reset-cycles
  + 2`, `xprop` `--depth >= reset-cycles + settle + 3`, `from-sim` `--depth >= 2`.
- `--tie PORT=VALUE` works in every flow; `ties`, `reset` and `restrictions` (ties, reset sequence,
  inputs assumed defined) are recorded in the result.
- Every name (top, clock, reset, tie ports, scope, `--signal`, names from the checks report), the engine
  and every path is checked against a strict pattern before a Yosys/sby script is written: names are
  identifiers joined by dots; paths may only contain letters, digits and `_ . / + @ % , = : ~ -` (a path
  with a space is rejected). A bad name is an input error (exit 2). For a bad name from the checks
  report (older reports had empty path segments, `tile.frontend..io_x_valid`), the message says to
  regenerate the report. Clock, reset and tie ports must be inputs of the toplevel, `--signal` must exist
  in the flattened design. `--reset` defaults to `reset` if the toplevel has it.
- By default, one clock only. sby runs with `multiclock off`: one solver step is one cycle of every flip-flop, memory
  port and clocked assertion. Before the proof, every flow runs a Yosys clock probe on the flattened
  design (`clock_probe.ys`, `clock_cells.json`) and refuses (exit 2, no `result.json`) a design where any
  enabled clock or trigger input is not the rising edge of `--clock`: a second clock, a gated or derived
  clock, a falling edge, a constant clock. Such a design would otherwise be proven as if all its clocks
  ticked together (a false pass). Asynchronous memory read ports and unclocked assertions have
  no clock and are accepted. Asynchronous state (async reset or set, `$adff`, `$aldff`, `$dffsr`, `$sr`)
  and latches are refused the same way: the single-clock model misses a pulse between edges.
- With `--json`, stdout is the result document only; notes (e.g. `bmc` on a toplevel without a reset)
  go to stderr. `result.json` is the same document.
- `--timeout` (and an MCP cancel) stops yosys, sby and the solvers: they run in their own process
  group; sby gets SIGTERM and stops the solver groups it started, then SIGKILL after 10 s (below the
  MCP job's 15 s SIGTERM-to-SIGKILL grace, so the CLI is still alive to finish the stop).

### `rvw formal from-sim` (start a proof from a simulation state)

1. Streams the trace (FST through `fst2vcd`, or VCD) up to the requested state, the values right after
   the N-th rising edge of `--clock` (or `--time T`), and stops reading there. Keeps the variables under
   the toplevel's scope and hoists Verilator's memory sub-scopes (`mem.mem[3]` becomes `mem[3]`, which
   is what Yosys expects). Writes a one-timestamp `state.vcd`. A `--time` before the first or after the
   last recorded timestamp is an error (exit 2, the message gives the recorded interval).
2. `yosys: prep; setattr -unset init; (drop memory init contents); async2sync; sim -clock clk -r state.vcd
   -scope <top> -at <T> -w; write_rtlil` gives every register an `init` and every memory an `INIT` from
   the trace. The RTL's own initial values (`initial` blocks, memory init contents) are dropped first:
   they hold at time 0, not at cycle N, so state missing from the trace starts free (any value) instead.
3. SymbiYosys BMC over `state.il` with the reset tied inactive (`delete -input` + `connect -set`), other
   inputs free unless `--tie PORT=VALUE`. Step k is cycle N+k; a clocked assertion (all of Spinal's)
   reported at step k failed on the values of cycle N+k-1, which is the `cycle` reported.
4. Reports where the start state came from, bit by bit (`state` in `result.json`): `ff_bits_from_trace`,
   `ff_bits_free` (not in the trace: any value; the first names in `registers_free`) and `ff_bits_flow`
   (registers the flow adds and starts itself: async2sync's assertion samplers start disabled), out of
   `ff_bits`; `mem_bits_from_trace` of `mem_bits`, and the memories with no traced word (`mems_uninit`).
   Free state can only add behaviours: a pass still holds, a failure at the first steps may be spurious.

Memories: `--memories trace` (default) takes contents from the trace; memories absent from it stay
free (any contents). Verilator only dumps arrays up to `--trace-max-array` words (default 32) and signals
up to `--trace-max-width` bits (256), and skips names that start with `_` unless `--trace-underscore`:
set all three for the simulation (the BOOM runner does). `free` drops
all contents (sound, may give spurious failures: the test suite shows a property that holds from the
traced memory and fails with free memory); `zero` fills words the trace did not give with zeros.

### `rvw formal xprop`

Flattens the design, brings the targets out as ports (`expose`), runs Yosys `xprop -split-outputs`
(registers and memories without init are X; inputs assumed defined) and asserts in a wrapper that no
target is X once reset is over: toplevel outputs (`--outputs`), and from a checks report every
Stream/Flow `valid`, `ready` while valid and (`--payload`) payload while valid. That is where Spinal's
knowledge helps: a payload is allowed to be X while `valid` is low.

## Demo and evidence

`scripts/demo.sh` (log of a run: everything below).

1. Simulation (`ChecksDemoSpec`, 8 tests): the clean `ChecksDemo` has all 7 stream/memory/index/enum/
   progress kinds inserted (20 checks; in formal 18 are assertions and the 2 rules on the toplevel's
   input stream are assumptions) and nothing fires in 3000 random cycles; each of the 6 planted bugs
   fires exactly its check; waivers/disables remove checks and are reported. `ArmingSpec` (2 tests):
   the first written illegal index fires, an unwritten register's illegal power-up value does not.
   `TileLinkSpec` (5 tests): the TileLink burst rule.
2. BMC from reset, depth 25 (yices), 18 assertions: clean passes; `hold`, `stable`, `mem`, `vec`, `enum` each fail
   with only their check, at steps 5 to 10, in about 2 s, reported as e.g.
   `FAIL mem.index:mem_port0_write at step 7 (cycle 6) ChecksDemo.v:412 [Demos.scala:44]`. `hang` needs
   ~240 cycles and passes at depth 25 (the simulation monitor catches it).
3. xprop: on the clean design, X reaches `io_memOut` (a read of a memory word never written: true)
   and `io_aux` (the two registers deliberately left without reset);
   with the planted `xvalid` bug (a stream valid gated by a register without reset, invisible in
   Verilator's 2-state simulation), X is found first on the internal stream `stage`'s valid at step 4
   and then followed through the FIFO to `io_out`.
4. Deep bug (`DeepBugDemo`: a 6-entry queue in a non-power-of-two memory; valid is withdrawn while
   stalled only when exactly 2000 packets were served and the head packet is 0x5A):
   - random simulation, 9000 cycles: 2333 packets served, the bug is not hit;
   - BMC from reset, depth 30: passes (2.7 s), the bug is ~7700 cycles deep;
   - from-sim at cycle 7680 (served = 1990), depth 30: fails at cycle 7691,
     `stream.valid_hold:io_out [Demos.scala:101]`, in 2.6 s, with 56/56 register bits and 1/1 memory
     loaded from the trace. The counterexample shows served = 0x7d0, head = 0x5a, ready low, valid
     dropped. From cycle 3000 the same BMC passes.

## BOOM (`boom/`)

A separate sbt build over the spinal-boom clone (`SPINAL_BOOM`, default `../../../spinal-boom-eda`):
`BoomChecks` elaborates `boom.system.BoomSimTop` with the checks phase and runs ELFs through the clone's
own harness (`boom.sim.BoomSim.run`: TileLink memory agent with randomized timing, `tohost`). Nothing in
the clone is edited. BOOM-specific settings: the retirement watchdog on `io_trace_insns_*_valid`
(20000 cycles) and `boom/waivers.txt`. Both scripts take the machine-wide `boom` lock.

```sh
SpinalChecks/boom/run-suite.sh small out/suite-small   # rv64ui-p-* + median, qsort, towers, dhrystone
SpinalChecks/boom/from-sim.sh 1440 4 out/fs2-small     # simulate with waves, then BMC from cycle 1440
# results: boom/out/<dir>/summary.txt, summary.json, tests/<elf>.json; from-sim-*/result.json
```

`BoomChecks run` requires `monitor` or `both` after it applies `SPINALCHECKS_MODE`.
A firing check makes a program fail even if `tohost` reports a pass. The runner writes its
reports, then exits 1 if any program did not pass.

`boom/from-sim.sh` builds BoomSimTop with the checks as asserts and monitors (`--formal --mode both`),
simulates rv64ui-p-add with an FST of the whole state, and runs `rvw formal from-sim` from cycle N.
TileLink D/B `valid` and the interrupts are tied to 0; A/C/E `ready` stay free. The script passes
caller values as shell arguments, quotes file arguments and refuses unsupported sbt paths before
simulation. It returns the failure status of the formal command. `boom/xprop.sh` runs xprop on
BoomSimTop with targets from the checks report.

Set `ENV_SH` to the core environment script before using these BOOM helpers.
Set `RISCV_TESTS` to the built ISA test directory for `run-suite.sh` and for
`from-sim.sh` when it runs simulation. `SKIP_SIM=1` uses existing artifacts.
`BENCH_DIR` defaults to `examples/boom/out/arch/bench` in this checkout.
The scripts reject missing required settings. For example, from the repo root:

```sh
export ENV_SH=/path/to/boom/env.sh
export RISCV_TESTS=/path/to/riscv-tests/build/isa
SpinalChecks/boom/run-suite.sh small
```

Earlier measurements on BOOM `small`, seed 1:

- Simulation of 58 programs (measured 2026-10-23): 516 checks, 484 inserted, 32 waived, 24 fire. The firings are
  candidates for triage, not confirmed core bugs. 57/58 programs pass `tohost`; `rv64ui-p-ma_data`
  fails, also without checks.
- from-sim on rv64ui-p-add from cycle 1440 passed at depths 4 and 16, and BOOM xprop reported 367
  candidate X targets. These ran with earlier flows and were not repeated. No BOOM proof validates the current flow.

## Decisions

- **A phase, not a wrapper.** The checks are inserted by a Spinal phase (`SpinalConfig.phasesInserters`)
  right before `PhaseCheckIoBundle`: names are known, and the inserted logic still goes through clock
  domain pulling, width inference and the usual checks. Works for `generateVerilog` and `SimConfig`
  alike, and needs no change to the design (BOOM's sources are untouched).
- **Which streams.** Every Stream port and selected internal stream. A producer can use consumer
  checks only for full direct assignments: `valid` and every matching payload field go into the
  consumer, and `ready` comes from that consumer. Each target must have one full, unconditional wire
  assignment. The components must use the same clock domain, and the payload directions and TileLink
  channel rules must match. All required consumer checks must be enabled and not waived. Otherwise the
  producer checks stay. Top input assumptions cannot cover a child assertion. Coverage chains must end
  at retained checks; cycles keep all checks. An exact consumer waiver does not waive a producer check.
  Looser rules missed a parent stream with `ready` tied low and a toggling child master; both gave
  a false BMC pass (`ReadyWiringSpec`, `ChildMasterSpec`). This rule can keep duplicate checks for
  equivalent logic that is not a direct connection. Checking only producers would miss streams built
  by hand in the parent.
- **Vec reads are found as multiplexers.** `Vec(a, b, c)` does not set element parents, so Vecs cannot
  be found from signals; every dynamic Vec read is a Spinal `Multiplexer` with the index as select.
  Direct conditional uses are gated by their enclosing `when` scopes.
- **Enum encodings** are resolved when the phase runs (native becomes binarySequential, as Spinal's
  Verilog backend does); the legal check compares the full bit pattern, so one-hot multi-hot values fail.
- **Source locations** need Spinal's `debugComponents`, so `withLocations` elaborates the design twice:
  once up to naming to learn every component class (as SpinalWaves does), then the real elaboration.
  Without `withLocations` there is one elaboration and no source lines. The innermost frame outside
  Spinal and this library is reported; for StateMachines, the StateMachine's own location.
- **Waived checks are not inserted** (they cost nothing); the report still lists them.
- **Monitor state is read with `simPublic`** rather than ports, so no IO is added to any component.
  SpinalSim's own simPublic phase runs before ours, so the phase also adds `Verilator.public`.
- **Simulation reports need monitors.** Assert mode prints simulation messages but has no firing
  counters. The report APIs refuse it. The BOOM runner also refuses it after environment overrides.
  A monitored check failure makes the run fail.
- **Arming by writes.** Arming on the first change of value missed the first illegal value. A
  `chk_<reg>_write` wire is False at the head of the body and True in every outermost scope that
  assigns the register. A register assigned from another component's scope falls back to "changed
  value", combinationally. A partial assignment (`r(3 downto 0) := ...`) arms the whole register.
- **TileLink channel semantics.** Strict Stream rules are retained in the report with a
  protocol reason. TileLink burst and transaction rules remain active. The beat protocol belongs
  to a `tilelink.Bus`, not to the message type.
- **Waivers are exact ids.** A glob can silently remove checks that never fired (and the other kind of a
  stream); `boom/waivers.txt` lists one id per fired and triaged check.
- **Ids are unique per instance.** Ids use identity paths made distinct among siblings before any id
  is formed. Objects are made distinct within a component. A repeated id is an error. Without this,
  two unnamed siblings shared one id, and one exact waiver waived both. Predicting Spinal's final names
  instead was rejected: they are allocated after the checks are inserted, against definition and enum
  names in a global scope. Cost: loop-built siblings get different `[spinalchecks] FIRE <id>` messages,
  so Spinal does not merge their definitions (`Stage`, `Stage_1`).
- **Report names come from the final netlist.** Components created in a loop body are unnamed when the
  checks are inserted. The report takes paths after name allocation, and ids use the class name as a
  placeholder. `xprop` refuses a report name it cannot use (exit 2, regenerate the report). A bad
  `--signal` is also an error.
- **`rvw formal` lives in `rvw`** (`rvw/src/rvw/formal/`), Python standard library only, `--json` on every
  command, results in `result.json`. The [formal package README](../rvw/src/rvw/formal/README.md) has
  its input capture, tool, reachability and replay rules.
- **Default engine yices.** bitwuzla stalled at step 19 on `ChecksDemo` (minutes per step) where yices
  takes 4 s for depth 25; on `DeepBugDemo` bitwuzla is ~40x faster than yices. Choose with `--engine`;
  an engine portfolio is FV item 1. `smtbmc:abc` is unsupported: this Yosys 0.64+174 release
  crashes in its ABC SMT parser on a small counter. `rvw formal` refuses it before proof.
- **Step to cycle.** Spinal's asserts are clocked, so sby flags them one step after the cycle in which
  the condition held. `rvw formal` corrects cycles only when Yosys property metadata confirms
  that delay. Unclocked or ambiguous properties retain the solver step and have `cycle: null`.
- **from-sim drops the RTL's initial values.** Yosys `sim -w` keeps a register's `init` when the trace
  does not have it, so a register missing from the waveform starts at its time-0 value and can turn a
  failure into a pass. All `init` attributes and memory init contents are removed before the state is
  loaded. Only async2sync's assertion samplers keep theirs, marked `rvw_flow_init` and counted as
  `ff_bits_flow`.
- **One run per output directory.** Two runs on one `--out` share the wrapper, the `.sby` file and the
  solver directory, so one run can prove the other run's wrapper (a false pass). A busy directory is
  refused at once (exit 2), not waited for: a wait could block for the length of a proof, and a nested
  call in the same process would wait for itself.
- **Formal inputs are rejected rather than escaped.** Yosys and sby scripts have no reliable quoting, so
  names and paths outside a strict character set are errors (paths with spaces included).
- **Explicit clock and state models.** Default flows require one rising-edge clock and synchronous
  state. BMC can opt into the sampled event model below. It separately enables constant-value async
  reset FFs. Other unsupported clocks and state remain input errors. Each flow checks elaborated state
  before optimization, ties or replay loading. Asynchronous memory reads remain supported; memory
  async reset ports must be tied to zero. Refusal exits 2 and removes any old `result.json`.
  The async-reset false-pass regression remains refused by default.
- **No pass without a checked assertion**: zero assertions is `no_checks`; too shallow a depth is an
  input error. The minimum depths are exact for clocked assertions (tested: the minimum depth finds a
  failure possible in the first cycle after reset).

## Channel semantics and bus checks

Use `ChecksConfig(mayDropValid = Seq(StreamSemantics("path.stream", "reason")))`
for a Decoupled producer. The pattern matches the stream identity path without
its check kind. This setting permits both withdrawal and replacement before
acceptance. It removes the two strict Stream rules. The report retains both
records and their reason. A reason is required. Use `SPINALCHECKS_STREAMS` to
load a file with one `<pattern> <reason>` per line. An exact check ID, such as
`stream.valid_hold:path.stream`, changes only that rule. The payload rule stays
active. Use `stream.payload_stable:path.stream` to permit payload changes only.
BOOM data belongs in `boom/streams.txt`. Use exact check IDs there. Each reason
must cite the producer and receiver sources. Generic code does not identify
BOOM streams. These settings do not change TileLink burst or transaction rules.

TileLink bus channels use protocol semantics automatically. An unaccepted offer
can change. `tilelink.burst_stable` still checks accepted multibeat messages.
A Stream that only carries a TileLink payload remains a strict Stream.

The checks target the TileLink subset in SpinalHDL 1.15.0. Its A opcodes are
Get, PutFullData, PutPartialData, AcquireBlock and AcquirePerm. Hint and atomic
opcodes are absent from this library version. A/D bookkeeping checks source
reuse, response opcode and response size. It permits responses in the first
request cycle. A source is released on the first accepted D beat, as in Rocket's
TLMonitor. AcquireBlock permits Grant or GrantData. AcquirePerm requires Grant.
C/D bookkeeping checks Release source reuse and ReleaseAck size.
D/E bookkeeping checks Grant sink reuse and unmatched GrantAck. Reset clears
all bookkeeping. Source and sink widths above eight bits are rejected.

AXI address checks target AXI4, including omitted optional fields. They check
transfer size, reserved burst encoding, FIXED length, WRAP length and alignment,
and the INCR 4 KiB boundary. WRAP length uses beats minus one. AXI3 is rejected.
Declare `readIssuingCapability` or `writeIssuingCapability` to add transaction
checks to `Axi4`, `Axi4ReadOnly` and `Axi4WriteOnly`. Each limit must be in 1..32.
ID width must not exceed four bits. Read queues check RID, per-ID response order,
RLAST and EXOKAY. Write queues accept AW and W independently. They check burst
length, BID and EXOKAY. B responses can reorder across IDs. Queue overflow is a
reported capacity failure. Reset clears all queue state. A bus without a positive
limit gets a report note and address checks only. Shared ARW buses are not tracked.
The checks do not establish data correctness or complete AXI compliance.
AXI4-Lite has a separate Spinal type and is not discovered by these AXI4 rules.

The small reference designs are in the protocol and reference `*Spec` files. Run them with `sbt test` under the `sbt` lock.
They inject legal offer changes, source reuse, unmatched responses, response
opcode and size faults, parameter faults, and AXI address faults.

## Gaps

- Flow payload legality needs a project-declared allowed set; there is no generic handshake rule.
- Index use inference supports local wires, mux branches, literal switch scopes and asynchronous
  memory reads. Unknown and cross-component uses remain conservative.
- TileLink: probe tracking, negotiated transfer capabilities,
  B/C parameter checks and coherent memory scoreboards remain open. Bus checks do not prove
  end-to-end data correctness. `spinalchecks.sim.TileLinkReference` reuses Spinal's
  `MasterDriver` and `Monitor`. Its separate memory scoreboard checks Get/Put data,
  masked writes, response reordering and declared denials. Initialize every read byte.
  The model serializes operations at complete A acceptance. Concurrent overlapping
  operations need a separate ordering model. Coherent traffic is rejected.
  `TileLinkReferenceSpec` connects this model to a small memory with backpressure.
- AXI4: full exclusive monitor behavior and Shared ARW tracking remain open.
  `spinalchecks.sim.AxiReference` uses Spinal's master with a separate byte model.
  `AxiReferenceSpec` connects it to Spinal's subordinate memory model. It tests INCR
  bursts and a DMA copy with response delays and interruptions. The helper serializes
  memory operations. Concurrent overlapping memory traffic needs an ordering model.
  AXI4-Lite needs its own explicit rules and reference designs.
- Dynamic bit reads have range checks; unknown consumer uses remain conservative.
- Components without reset: checks there are always active.
- `rvw formal x-sweep` inventories module outputs with bounded jobs and native Icarus replay.
  Use `xprop --combinational` for a clock-free wrapper. See the
  [formal commands](../rvw/src/rvw/formal/README.md#x-campaigns-and-four-state-replay) for dispositions.
  Module inputs are free; a confirmed module observation does not establish a core bug.
- BMC's event model supports independent rising-edge top clocks and optional constant-value
  async-reset state. Gated, derived and falling-edge clocks remain refused. Other flows retain
  the one-clock model. Async loads, set/clear and latches remain refused.
- Streams in a component with registers in another domain are refused. Use child components.

- Designs with more than one clock (or a gated clock, or registers on the falling edge) are refused by
  every `rvw formal` flow; there is no multi-clock model yet.
- Asynchronous state controls and latches are refused by every `rvw formal` flow. There is no model
  for their events between clock edges.
- Stream checks still use the component domain. Project-declared rules use their binding domain.
- from-sim: signals Verilator does not trace (optimized away) start free; the report counts them. This
  includes registers with an RTL initial value.
- Two sby runners: `rvw/src/rvw/formal/common.py` (`run`, through `rvw.common.proc.run_group`) and
  `rvw/src/rvw/cov/proof.py`; merge them into one.

## Limit ownership

Check rules: [#65](https://github.com/riscPrint/risc-v-workstation/issues/65). Protocol coverage: [#66](https://github.com/riscPrint/risc-v-workstation/issues/66). BOOM dispositions: [#5](https://github.com/riscPrint/risc-v-workstation/issues/5). Multi-clock/async formal: [#46](https://github.com/riscPrint/risc-v-workstation/issues/46). Shared runners: [#117](https://github.com/riscPrint/risc-v-workstation/issues/117). X campaigns: [#67](https://github.com/riscPrint/risc-v-workstation/issues/67).

Retained limit: The documented TileLink/AXI subsets, queue capacities, free replay state, clock-domain placement and index-check behavior remain bounded restrictions. Reference traffic does not establish complete protocol compliance or coherent ordering.

## C reference datapath checks

See [c2rtl/README.md](c2rtl/README.md) for the native C truth-table and
SymbiYosys flow. It supports unsigned combinational units with widths 1 to 4.
It reports proved, counterexample or inconclusive with the checked bound.

## Counterexample what-if replay

`rvw formal cex --result OUT/bmc --edit bad@0=0 --out OUT/whatif` replays a
captured BMC witness with Yosys `sim`. It keeps the original inputs and constraints.
It writes VCD/FST and can call SpinalWaves, Surfer and SpinalTrace with matching
metadata. Replay never earns a proof pass. See the [command guide](../rvw/src/rvw/formal/README.md#counterexample-what-if-replay)
for edit syntax, result meanings and validation limits.



### Shared solver execution

Formal probes and coverage exclusion jobs use `rvw.common.sby.execute`.
The shared runner writes the combined log and stops the process group on timeout
or cancellation. It gives SBY 10 seconds to stop its solver sessions.
Each caller keeps its captured environment and tool bindings.
Formal still checks the DONE line, process exit and assertion count.
Coverage still checks its captured status, source snapshot and vacuity evidence.
A timeout cannot earn a proof or an exclusion.

## Multiple clock domains and asynchronous reset

`rvw formal bmc --event-model` uses SBY `multiclock on` and Yosys `clk2fflogic`.
Declare every extra independent rising-edge top input with `--event-clock PORT`.
Enable constant-value asynchronous-reset flip-flops separately with `--async-reset`.
All other formal flows keep their current clock and state refusals.

```sh
rvw formal bmc --verilog SpinalChecks/examples/events/clocks_fail.sv --top top --event-clock other_clk --depth 14 --out out/clocks
rvw formal bmc --verilog SpinalChecks/examples/events/async_fail.sv --top top --event-model --async-reset --depth 14 --out out/async
```

Both examples must fail. Their `*_pass.sv` peers must pass at the same bound.
The clocks have no rate, phase or fairness constraints. One solver step is one
global input sample. The model includes inter-edge reset pulses that remain
visible for a sample. Pulses entirely between samples are outside the model.
It does not establish analog CDC behavior or physical reset recovery/removal.

Enum-register checks use the register's Spinal clock domain. Vec checks whose
selector is a register use that register's domain. Memory checks retain the
memory port's domain. Their reset gating, assertion and monitor state use the
same domain. Monitor cycle counters are local to each domain. Stream, bus,
combinational-selector and progress checks still use the containing component's
domain. Place these interfaces in a component with the correct domain.
A component with streams, a combinational Vec selector, or a progress check
and registers in another domain
is refused. Use child components for these domains. The phase does not infer
a stream's domain from its wiring.

Inserted checks report `clock_domain` with clock, edge, reset, reset kind, reset
active level and clock-enable names. This records Spinal's domain information.
It does not declare relationships between domains or replace the RTL clock probe.
See [the formal event model](../rvw/src/rvw/formal/README.md#sampled-event-bmc)
for reset sequencing, result meaning and the full refusal list.

Formal generated assertions sample on clock edges even when the state has an async
reset. Reset still gates the check. Formal mode omits monitor text reports.
Raw assertions with an async reset in their sensitivity list remain refused.
Their trigger semantics are outside this increment.

### Sequential equivalence

`rvw formal equiv` compares two exported RTL revisions with eqy and native ABC.
It supports one clock, aligned synchronous reset, automatic register names and
manual pairs. Unknown partitions and unmatched state stay inconclusive. See the
[formal README](../rvw/src/rvw/formal/README.md#sequential-equivalence-first-increment-issue-18)
for the result contract, tests and limits. Issue #18 remains an epic.

## Project-declared checks

Call these APIs from the project wrapper during elaboration. Install SpinalChecks
on that wrapper. Use the sampling `ClockingArea` for each binding. The phase adds
normal check records, exact IDs, waivers, assertions and monitor counters.
`DeclaredChecks.rule(kind, name, detail)(failure)` is the low-level binding API.
It does not infer intent. A missing binding does not establish checked behavior.

`DeclaredChecks.flowValues(name, flow, allowed)` checks a `Flow[Bits]` payload
against a nonempty declared set on valid beats. No rule requires a Flow to hold
valid or payload between beats. Each call captures its current clock domain.

Dynamic bit reads on non-power-of-two widths produce `bits.index` checks.
Vec and bit-read checks use the enclosing `when` conditions. An unused read in
an inactive direct assignment does not fire. Local uses through intermediate wires,
expression multiplexers, literal `switch` scopes and asynchronous memory reads
are gated. Unknown uses remain conservative. A register select or bit source supplies the clock
domain; otherwise the component domain is used. Each domain has its own monitor
cycle counter. Existing `NamingSpec` tests keep loop-built IDs distinct.

Connectivity and CSR applications are selected as explicit project bindings.
Deadlock generation remains deferred to #21. This choice does not add automatic
application discovery or core-specific rename, LSQ, ROB or issue bindings.
Run `sbt "testOnly spinalchecks.LocalRulesSpec spinalchecks.NamingSpec"` under
the `sbt` lock for the local rules.

### Architectural CSR model

`CsrChecks.bind` accepts a version-1 `CsrModel` and independent accepted access
signals. The model declares width, reset, write mask, minimum privilege and an
optional allowed-value set. Unwritable bits retain their value. A masked candidate
outside the set is rejected. Hardware clear follows the software update.
Hardware set has final priority. Expected state starts at the declared reset.
The model never initializes expected state from the DUT.

For example, `CsrModel(1, 32, 0, 255, 3)` declares eight writable bits and machine
access. Bind the observed state, read/write requests, write data, privilege,
access-denied response, hardware-set mask and hardware-clear mask, in that order.
Requests must include denied attempts so that `csr.access` can check the response.
`csr.state` checks the state each active cycle. Optional disjoint `w1cMask`
and `readClearMask` declare side effects. A read clears before a software write.
The `legalize` table maps masked candidates to legal WARL values. Unmapped illegal
candidates retain state. `wlrl=true` instead requires a denied response to an illegal
candidate. This is an explicit project policy. `readOnly=true` denies every write.
Individual read-only fields stay outside both write masks. Optional `readData`
checks granted reads against independent state before side effects. These models do not
decode CSR instructions or bind aliases. Run `sbt "testOnly spinalchecks.CsrChecksSpec"`
under the `sbt` lock. The reference injects state and access faults separately
from the expected-state model. No BOOM CSR binding is supplied.

### HPM count model

`HpmChecks.bind` accepts `HpmModel(1, width, reset, eventMeaning)` and the observed
counter, independent event count, inhibit, permitted filter, software write and
write data. It checks `hpm.count`. Write has priority over counting. Arithmetic
wraps at the declared width. Each project must state the event meaning and bind
an independent observation. A DUT event output alone does not supply an oracle.

Run `sbt "testOnly spinalchecks.HpmChecksSpec"` under the `sbt` lock. This model
covers count transitions, inhibit, filtering, writes and modular wrap. It does not
check event selector CSRs or counter interrupts. `bindAccess` checks denied
responses from privilege and independently observed counter-enable bits. Requests
include denied attempts. The read-only alias denies writes at every privilege.
The machine alias permits writes only in machine mode. Gate the count model's software writes with its returned
permission. `bindHalfRead` checks a selected RV32 half against an independent
64-bit expected counter. Bind accepted responses at the same sample. It does not establish full Zihpm compliance. No core binding is supplied.

### Value connectivity model

`ConnectivityChecks.bind(name, source, destination, enable, latency)` checks equal
width values at a nonnegative fixed latency. Each enabled sample creates an
obligation. Enable is sampled with the source and delayed with its value.
Reset clears pipeline-valid state. Mode conditions can be included in enable.
Run `sbt "testOnly spinalchecks.ConnectivityChecksSpec"` under the `sbt` lock.
The reference has zero-cycle and one-cycle paths with injected transfer faults.

This emits `connectivity.value` assertions for simulation or a formal backend.
Simulation checks exercised transfers only. It is not a structural proof.
`rvw formal connectivity` resolves required and forbidden endpoints through
SpinalDB. Its optional native campaign checks bounded top-port transfers and
forbidden influence. It retains unresolved endpoints, opaque cones and limits
as incomplete. See [the formal command guide](../rvw/src/rvw/formal/README.md#declared-connectivity-107).
General internal RTL binding and core qualification remain open under #107.
No proof result is inferred from successful elaboration or simulation.

### Device register transactions

`RegisterChecks.bind` uses a version-1 `RegisterModel` with width, reset,
ordinary-write mask, W1C mask and read-clear mask. Ordinary and W1C masks must
be disjoint. Bind observed state, accepted read/write, data, strobes expanded to
bit enables, and independent hardware-set and hardware-clear events.
The update order is read-clear, software write/W1C, hardware clear, hardware set.
Unwritten bits retain their independent expected value. Reset uses project data.
The model never copies expected state from observed state.

Run `sbt "testOnly spinalchecks.RegisterChecksSpec"` under the `sbt` lock.
The reference uses separate per-bit logic and injects an observed-state fault.
Optional `response`, `responseValid` and `latency` bindings check read response
data against expected state before read-clear. Each accepted read must produce
one response after the declared fixed latency, including back-to-back reads.
This does not check address decoding, variable response latency or bus ordering.
A project must supply those bindings and test its address decoder. Architectural CSRs use `CsrChecks`, not this device-register model.

### Imported SVA subset

`rvw formal bmc --frontend slang` supports a restricted native SVA import path.
See [the subset and sampling rules](../rvw/src/rvw/formal/README.md#imported-sva-through-slang).
It includes inline clocked Boolean properties, `disable iff` and single-argument
sampled value functions. Temporal implication, sequence delay and repetition remain
unsupported. The SBY campaign runner does not depend on this frontend.

### Register-map imports

Run `scripts/import-map.py ipxact INPUT.xml OUTPUT.properties` with Python 3.
For SystemRDL, install `systemrdl-compiler==1.33.0` in your environment and run
`scripts/import-map.py systemrdl INPUT.rdl OUTPUT.properties`.
The SystemRDL compiler elaborates the source. The importer does not parse RDL with
regular expressions. `RegisterMap.load(new java.io.File(path))` loads the result.
Each entry has an address and a `RegisterModel`. Use `entry.csr(minPrivilege)`
for an architectural CSR model. Declare WARL/WLRL policies in project data.
Bind independent transaction and hardware observations with the existing APIs.
No bus or CSR binding is inferred from a map name.

The supported subset has explicit field resets, ordinary writes, read-only
fields, W1C and read-clear. IP-XACT uses byte addresses, explicit bit offsets and
widths, and one complete reset per field. SystemRDL uses elaborated register
addresses and bit positions. Unsupported side effects and listed unsupported
constructs raise an error. This is a subset importer, not general standards
compliance. Parameterized IP-XACT, register files, alternate registers, aliases,
write constraints and vendor extensions need a separate adapter. The examples
in `src/test/maps/` describe equivalent maps in both formats.

Index use inference follows local combinational wires, expression mux branches,
literal switch cases and asynchronous memory read consumers. Unknown expression
uses and cross-component uses stay conservative. Masked switch keys and general
clock-domain inference remain open. Local use checks do not prove application
coverage or non-vacuity.
