# rvw cov

Code coverage and test selection for any Verilator design; architectural functional coverage for
RISC-V C2 traces; reviewed proof exclusions and MCY mutation reports. BOOM-specific test lists
and commands stay in its adapter and the examples. No hardware writes are involved.

From the repository root:

```sh
cd rvw && uv venv && uv pip install -e '.[dev]' && cd ..
source ../spinal-boom/env.sh
rvw/.venv/bin/rvw cov --help
```

Every leaf command accepts `--json` and `--out FILE`. With `--json`, stdout is exactly one JSON document: the result, or on failure the structured error
(`rvw.coverage-error/1`, also when the result itself cannot be written as strict JSON), with exit 2.
An input capture failure returns `status: inconclusive`, cause `input_not_captured:<name>` and exit 3.
Mutation reports also exit 3 while their external script dependencies remain incomplete,
or if MCY execution fails. A completed MCY report with error rows exits 1.
Commands use standard-library Python, with external tools only for `.dat`
export, proof execution and mutation execution. Coverage reporting needs no installed simulator.

## Code coverage

```sh
rvw/.venv/bin/rvw cov merge add=runs/add/coverage.dat mul=runs/mul/coverage.dat \
  --source-root /path/to/generated/rtl --revision BASE --out coverage.json --dat merged.dat --json
rvw/.venv/bin/rvw cov merge suite/results.json --out coverage.json --json
rvw/.venv/bin/rvw cov report coverage.json --annotate holes --out report.json --json
rvw/.venv/bin/rvw cov rank coverage.json --out ranking.json --json
rvw/.venv/bin/rvw cov rank coverage.json --exact --json
rvw/.venv/bin/rvw cov select coverage.json --repo /path/to/core --diff BASE..HEAD --json
```

Inputs can be explicit `test=coverage.dat`, C1 `result.json`, C3 `results.json`, or their parent
directories. Duplicate test IDs and incompatible point universes are errors. `.dat` export calls
the installed `verilator_coverage --write` and verifies its counts against the structured merge.
The database (`rvw.coverage/1`) retains original point metadata, stable SHA-256 point IDs,
per-test counts, raw artifact hashes and C1 provenance. Do not combine different instrumented
builds just because their filenames match. Raw files cannot supply missing revision/config/seed
provenance; use C1/C3 inputs for reproducible regressions.

Merge refuses inconclusive C1 runs and C3 entries under the shared result rule.
This includes changed input identity, harness errors, synthesized results,
wall-clock timeouts and unresolved concurrent-run attribution. Conclusive failures,
including cycle-limit timeouts, can still contribute coverage. Raw `.dat` inputs
have no run result to check; supply C1/C3 inputs to retain that evidence.

Saved databases receive the same C1 check. Report, rank and `.dat` export refuse
inconclusive evidence. For a changed revision, select returns all database tests
with `inconclusive_runs` in `fallback_reasons` and each cause in `inconclusive_runs`.
Such runs never contribute to `direct_tests`. `BASE..BASE` still selects nothing.

Reports count points, not lines: several branches or bit transitions can share one source line.
They include module summaries from Verilator's `page`, hierarchy summaries from `h`, Scala
locations, unmapped counts and every never-hit point. Verilator can collapse instances into
wildcard hierarchy; this is reported as aggregation, never invented per-instance attribution.
`types` and `module_types` separate line/branch/expression coverage from toggle coverage;
an overall percentage can otherwise be dominated by memory/register bits. Collection includes
reset and boot activity. Later runs stream counts against the first run's metadata, so merging
many million-point files does not retain a metadata copy per run. JSON output streams to disk.
`--annotate` publishes JSONL point details and numbered source text with `NEVER` markers
through a sealed generation in the chosen directory. The result names its generation in
`annotations`; `current` selects it atomically. A marker means at least one point on that line has no hits.

Ranking gives each test's hit and unique-point contribution. Default selection is deterministic
greedy set cover followed by redundancy removal: inclusion-minimal, not necessarily globally
minimum. `--exact` proves minimum cardinality by enumerating sets, bounded to 20 tests.
Zero-hit points cannot be covered by selecting any existing test and remain holes.

### Scala attribution

Spinal's `SpinalConfig(genLineComments = true)` emits assignment comments such as
`// @ Unit.scala l42`. Same-line comments and `Unit.scala:42` comments are read directly.
Verilator's `S` metadata lists statements covered by a point; comments within those exact
line spans are also used. Multiple Scala locations covered by one point are retained, so
Scala location counts must not be summed to get the design total. Unrelated neighboring
comments are ignored. A branch point without a location or recorded span remains unmapped.
Use `--scala-root /path/to/core/src/main/scala` to resolve bare comment filenames to unique
files. Duplicate basenames remain unresolved; the tool never picks an arbitrary source file.

`merge --hgldd path/to/top.dd` reads the SpinalWaves HGLDD dialect, with 1-based `file_info`
indexes. A variable's `value.sig_name`, owning `module_name` and `hgl_loc` map toggle points to
their Scala **declaration**. Explicit `hdl_loc` ranges, when present, also map to `hgl_loc`.
SpinalWaves currently emits source locations but often no HDL line locations; this cannot map
arbitrary branch conditions to statements. Struct/aggregate-only variables are left unmapped.
Mapping methods are retained on each point. Repeated `--hgldd` accepts multiple files.

An extraction tool can also supply an explicit `--source-map`:

```json
{"mappings":[{"verilog":"Unit.v","line_start":31,"line_end":33,
              "scala":"src/main/scala/Unit.scala","scala_line":42}]}
```

Use exact coverage filename spelling in explicit ranges. A mapping range assigns one source
location to its points; it does not imply a linear Scala/Verilog line offset. For absolute Scala
paths, change selection accepts an exact repository-relative suffix. Bare `Unit.scala` paths
cannot safely identify `src/.../Unit.scala` without an explicit map. `select` resolves each distinct
ref once to a commit ID. It uses those IDs for both changed-file and BASE-side zero-context
git diffs. The result keeps the requested range in `diff` and the full commit IDs in
`base_revision` and `head_revision`. A later branch move does not change that selection.
Evidence is kept per changed BASE line: every removed or modified line
must have a point mapped to it (`unmapped_lines`) that some test hit (`unhit_lines`); one covered
line does not vouch for the rest of its hunk. Lines a hunk adds beyond the ones it removes
(`added_lines`, including a pure insertion) have no BASE line to map. Any such line, unmapped
points and new files trigger a full-test fallback. So do a changed file that is not Scala (a Verilog blackbox,
`build.sbt`, a resource), a Scala file changed without a text hunk (mode change), and an empty
diff between two different commits; `fallback_reasons` names the causes. Only `BASE..BASE` (no
change) selects no test. Unknown revision, dirty C1 sources, or a C1 `core_rev` that does
not match BASE also trigger full-test fallback. C1 source cleanliness must be explicitly
`core_dirty: false`; missing/unknown cleanliness also falls back. Raw inputs need `merge --revision BASE` to
record their revision. Coverage collected from a different elaboration must be refreshed;
selection is a scheduling aid, not a proof that omitted tests cannot regress.

On BOOM, selection currently **always** falls back to all tests: 1 300 094 of about 1.34 M
Verilator points carry no Scala location (mostly
toggle points), and any unmapped point forces the fallback.

## Functional coverage

```sh
rvw/.venv/bin/rvw cov functional run-a/rvfi.jsonl run-b/rvfi.jsonl --out functional.json --json
rvw/.venv/bin/rvw cov functional functional.json run-c/rvfi.jsonl --out combined.json --json
rvw/.venv/bin/rvw cov functional run/rvfi.jsonl --config plan.json --json
```

Default groups cover mnemonic/class by privilege mode; trap and interrupt causes by mode;
RVFI trap-handler entry; memory read/write sizes and address alignment; CSR address/read/write/mode;
branch outcomes; RVFI `rd=0`; and dependencies on the immediately preceding retired destination.
Decoding uses the shared decoder `rvw/src/rvw/common/riscv.py` (RV32/64 IMAFDC, Zicsr,
Zifencei, Zba, Zbb and Zbs, with register banks: `fcvt.s.w` reads an x register, `feq.d` writes one). Reserved
encodings and RV64-only instructions on RV32 are `unknown`. Unknown instructions are counted explicitly;
this is not an ISA compliance checker. RVFI `rd=0` also denotes no destination. C2 `rd` is the
integer write only (0 when an instruction writes an FP register), so the `dependency` group takes
an FP destination from the encoding (`rd`, or `rd'` for `c.fld`/`c.flw`); a trace that reports an
integer `rd` for an instruction that writes an FP register contradicts the encoding, and the next
instruction's `back_to_back` is `undetermined` (when it reads any register). Memory masks
must be contiguous powers of two to receive ordinary alignment bins. Alignment follows the
trace's RVFI address convention, the platform key `aligned_mem` (`rvw/src/rvw/cosim/configs/`):
with `aligned_mem` (BOOM), `mem_addr` is the XLEN/8-aligned word and the access address is
`mem_addr` plus the mask's lane offset (`lh` at `0x80000001` is `mem_addr 0x80000000`, mask
`0b110`: misaligned). The platform is `--platform` (name or JSON, MCP `platform`), else the bundled
platform named by the header's `core`. Without one, or in a byte-address trace, a lane-shifted
mask is `undetermined` (never `aligned`); each trace records its `address_convention`. Branch
outcomes use operand comparisons, avoiding ambiguity when the target equals fall-through.

C2 trap events do not require a privilege field: absent modes are `unknown`. No mode is inferred
from a neighboring instruction. Dependencies reset at traps and between traces. Trace order
must increase, ISA/XLEN must match and duplicate trace content is rejected, including when
merging saved reports. Saved reports must use an identical coverage plan.
`handler_entry` measures RVFI `intr`, which marks both synchronous and asynchronous trap
handlers. `interrupt_cause_mode` uses actual C2 trap events with the interrupt flag instead.
The `retired` count includes all C2 instruction records, including `trap: true` records.
The [RVFI specification](https://yosyshq.readthedocs.io/projects/riscv-formal/en/latest/rvfi.html)
defines the handler-entry signal independently of asynchronous interrupt causes.

Default domains are a plan, not reachability assertions: machine-only cores will have U/S holes;
unsupported floating point will have float holes. Groups without declared bins report observed
values and cannot claim a completeness percentage. Add expected mnemonics, CSR addresses or
trap causes for the core's intended ISA/configuration in a declarative JSON plan:

```json
{"groups":[
  {"name":"mnemonic_mode","fields":["mnemonic","mode"],
   "bins":[["addi","M"],["mul","M"],["div","M"]]},
  {"name":"my_csr","fields":["csr","mode"],"when":{"class":"csr"},
   "domains":[["0x300","0x305"],["M"]]}
]}
```

Groups replace defaults with the same name, otherwise append. Set `replace_defaults: true`
to supply a complete plan. `when` supports field equality or `{ "in": [...] }`, `{ "min": N,
"max": N }`, and `{ "mask": N, "equals": N }`. Fields may be standard derived observations
or extra fields supplied by the core in C2. There is no expression evaluation. Each group
reports hits, expected-bin counts and holes across the merged traces.

## Proof exclusions

```sh
rvw/.venv/bin/rvw cov prove coverage.json --config proof-plan.json --work-dir proof-new --json
rvw/.venv/bin/rvw cov report coverage.json --exclusions proof-new/exclusions.json --json
```

`proof-plan.json` lists `sources`, `harness`, `top`, `depth`, `assumptions`, optional `reset`,
`reset_active_low`, `sanity_state` and `clock` (default `clk`), and `points` containing
`point_id`, a single SystemVerilog `expression`, and a `reason` linking the expression to that
coverage point. Paths resolve relative to the plan. The harness has one `// RVW_POINT` marker
inside its top module, usually within `always @(posedge clk)`. The tool inserts a `cover(expr)`
for a bounded witness search and independently `assert(!expr)` in unbounded `prove` mode.
Both run with SymbiYosys/smtbmc/z3. Sources need unique basenames and paths without whitespace.

Proof jobs use the `rvw formal` executable bindings. They keep the captured Z3 first in `PATH`,
also through the OSS CAD Suite Python launchers. `tool_bindings` records each executable and its
command adapter; `prove` checks both before it writes `exclusions.json`. An unsupported smtbmc
launcher gives `input_not_captured:tool:z3`, `status: inconclusive`, exit 3 and no exclusions.
The bindings also require Bash and `yices-smt2`; proof jobs use Z3.

A cover FAIL, depth limit, timeout or solver error **never** creates an exclusion. Only an
unbounded proof PASS with exit 0, no conflicting cover witness, zero simulation hits, **a
reached sanity cover and reached cone covers** can exclude a point. Every guard below must
also pass. What a guard does not model refuses. When a guard refuses, rows keep their
cover/prove results and get `refused`.

**Elaboration.** `prove` first runs Yosys with the same files in the same order and the same
front end as the jobs (`read_verilog -formal -sv`, no defines, files side by side as in the job's
`src/`), then `hierarchy -check -top <top>; proc; write_json` (`<work-dir>/guard/`). Instances,
port connections and harness inputs come from that netlist, never from the SystemVerilog text.
Macros, `` `ifdef `` branches, positional or `.*` connections, escaped names and comments mean
exactly what they mean to the solver. If Yosys cannot elaborate the harness, the guard refuses,
also with a stated `reset`. This Yosys drops `bind` statements, so a bound instance is in neither
the netlist nor the solver's model.

**Clock and state controls.** The SBY jobs model one clock. Every clock and trigger must use the
rising edge of the one-bit harness input `clock`. Other clocks, derived clocks, falling edges and
global-clock state refuse. The probe includes a sampled cover at the point marker and keeps
unused state. Asynchronous reset, set, clear and load controls, latches and unsupported state
cells also refuse, because the single-clock model misses pulses between clock edges. The check
reads every module after `proc`, before optimization can remove unused state or tied controls,
harness state included. An explicit `reset` or `"reset": null` cannot bypass it. Memory read
ports may be asynchronous, but their asynchronous resets must be tied inactive.

**Sanity cover (vacuity guard).** An over-constrained harness (reset held forever, contradictory
assumptions) proves every point unreachable. Before the points, `prove` runs, in the same harness,

```systemverilog
cover (!$initstate && <reset inactive> && !$stable({<state>}));
```

that is: after the initial step, every reset is released and some state changes. The state is the
plan's `sanity_state` (SV expressions), else the signals the point expressions read minus the
harness top's input ports (a free input always changes; they are listed in
`sanity.ignored_inputs`). Every name the state reads must be a net of the elaborated harness top.
Yosys turns an undeclared name or a hierarchical reference such as `dut.q` into a free wire, and
inside `$stable({...})` it does not warn. No point is excluded when the sanity cover is not
reached, reads an undeclared or undriven name, has no state to check (a point expression of
literals or harness inputs only), or no reset is found. A point whose own jobs read a free wire
is refused the same way. When the point signals legitimately never change (a stuck value), name
a signal that must move in `sanity_state`. `exclusions.json` records the check under `sanity`
with hashes. `report --exclusions` rejects files without a passing one.

**Resets.** With the `reset` key, the plan states the reset as a harness-scope expression.
`reset_active_low: true|false` is then required; the polarity is never guessed. `"reset": null`
states that the harness has no reset (an initial-state harness). Without the key, the guard
finds the resets in the netlist. A design instance is an instance of a module the source files
define, or a harness module without instances of its own; harness wrappers are walked through.
Its resets are the input ports that reset a register, and input ports named
`reset`/`rst`/`reset_n`/`rst_n`/`resetn`/`rstn`/`nreset`/`nrst`/`aresetn`. The polarity comes
from the registers after `opt_dff` (`guard/ffs.json`), never from the name. The guard collects
each bit of each reset-like input of every register, latch and memory cell (`SRST` of `$sdff*`,
including a synchronous clear `if (c) q <= 0`; `ARST` of `$adff*`/`$adlatch`; `SET`/`CLR` of
`$dffsr*`/`$dlatchsr`/`$sr`; `ALOAD` of `$aldff*`; the read-port resets of `$memrd_v2`/`$mem_v2`),
and every reset port of a submodule instance. A state cell type outside that list refuses.
A path that reaches an input port through `$not`/`$logic_not` only gives that port a polarity.
A path through other logic refuses when that logic reads anything from outside the instance's
own state: an input port (the `warm` of `if (reset || warm)`), a submodule output, or a free or
undefined value. Logic that reads only the design's own registers and constants (a counter
wrapping to 0) is design behavior, not a reset. A port whose registers all reset at one level has
that polarity, so a parameter that makes `reset` active low is seen. A port that resets no
register this way, or registers at both levels, refuses. Each reset connection is traced to a
harness-top name: a named net, a constant, `!`/`~` of one, or a wrapper input port traced to its
parent. `dut d(clk, hold, a, q)` gives `hold`; the list is in `sanity.instances`. A harness
declaration named like a reset is not used. Without a plan `reset`, the guard refuses when a
design instance has no reset port, a polarity is not established, a reset port is unconnected or
does not trace to a harness-top name (`.reset(a | b)`, a wrapper's internal register), or the
harness has no design instance. A reset through logic (`if (reset || flush)`, where `flush` reads
an input) also refuses, even when honest. State the whole reset (`"reset": "rst || warm"`); the
sanity cover then has to release all of it.

**Bound netlist and pinned state.** To see what the harness's connections do to the design, the
netlist also goes through `opt_expr; opt_dff` once per module (`guard/unbound.json`) and once
after `flatten` (`guard/bound.json`). There, a tie
can turn a plain input into a reset: `if (hold) q <= seed` with `.seed(1'b0)` is an `$sdff` whose
reset is the harness's `hold`. Every reset bit of every design register in the bound netlist is
traced through `$not`/`$logic_not` to a net of the harness top. A traced reset that is not yet in
the list joins the sanity cover (`sanity.bound.resets`, with the source locations of the
registers it resets). A bound reset bit that reaches no harness net and whose logic reads an
input or a free value refuses (`sanity.bound.untraced`). With a stated `reset` these bits are
recorded, not refused: the stated expression is the user's account of the resets. A design
register bit that is in the per-module netlist and gone from the bound one is pinned by the
harness (`.hold(1'b1)`: `opt_dff` replaces a register that is always in reset, never enabled, or
never leaves its initial value by a constant). Any such bit refuses, also with a stated `reset`
(`sanity.pinned`). The harness top's own registers are left out by source location; a location
shared with design code counts as design. Costs, all false refusals: a harness that ties off a
feature (`.debug_en(1'b0)`), and a design constant that crosses a module boundary into a register.
A register held through its enable or data by an assumption (not a tie) shows in none of these
netlists; the cone cover catches it.

**Cone cover.** The sanity cover shows that *some* state moves. That is not enough: with
`assume(seed == 0)` and `if (hold) q <= seed`, another register can move while `q` stays held.
So each point that its proof would exclude also needs a cone cover (`points[].cone`): every bit
the point reads must be able to change under the same harness. The guard's netlist (after `proc`,
not flattened) is traced from the names in the point expression through combinational logic and
instance ports to register and latch outputs, harness-top input ports and free values
(`$anyseq`, `$anyconst`). A register's own next-state logic is not followed. Each of these bits
(`cone.signals`, flattened names with bit positions from the LSB, as `d.q[3]`) gets one cover at
the point marker,

```systemverilog
cover (!$initstate && <every reset inactive> && !$stable(rvw_cone_<i>));
```

where `rvw_cone_<i>` is bound to the bit with `connect -set` after `hierarchy; proc; flatten` in
the job's script (a hierarchical name in the harness would be a free wire). The job (`<n>-cone`)
must reach every cover (status PASS), or the point is refused. The check is per bit, because a
hold on one bit of a wider register hides a hole too. The trace refuses (`cone.problems`, no job)
when the point reads a name the harness top does not have, a harness constant (a constant net, or
a constant tie on an instance port made in a harness module; a constant inside a design module and
a constant operand of logic are the design's), memory read data, an undriven bit, an instance
without a netlist, a source bit with no plain net name (or only a `[0:N]` one), or nothing at all.
It also refuses when the harness already has a net named `rvw_cone_*`, and when a module on the
instance path has a net with the bit's flattened name (an escaped `\d.q ` would otherwise be bound
in place of the register). Costs, all false refusals: a bit the design itself keeps constant (the
high bits of a counter that wraps early), a bit that needs more than `depth` steps to change, a
harness with `` `default_nettype none `` (the cover's wires are implicitly declared), and every
bit of a name the point reads, even when the expression selects one (`cnt[0]` reads all of `cnt`).
Limit: the cover shows that each bit can change at least once. An assumption that starts holding a
bit only after it has moved (`assume(!(cycle > 2) || hold)`) is not seen, nor is a relation the
assumptions keep between bits that each move (`assume(q == r)`).

**Cover isolation.** The sanity and cone jobs select only the covers that `rvw` generates. Each
generated cover has a property label. The script checks the label count, then removes other
covers from those jobs, so existing covers in the harness or DUT do not affect their status.
Every assumption and assertion stays in the jobs. Point cover and proof jobs keep the existing
properties.

**Inputs and snapshot.** Before any front end runs, the shared `Capture` reads the plan, database,
listed sources, harness and every literal `` `include `` dependency, including nested headers,
once. A private `input-capture/` directory in the work directory keeps the raw copies with their
original hashes. `source-snapshot/` holds the frozen RTL and its manifest: each include is
redirected to its captured header, and all other source bytes stay the same, including line
endings. The guard, sanity cover, point cover, proof and cone cover all read this snapshot, so a
live edit after capture (also an edit followed by a revert) cannot change the RTL a job reads.
The guard checks the `` `file_push `` paths in `read_verilog -ppdump` output against the snapshot.
A relative include must be one of the listed sources, because the solver runs in the job's `src/`,
which holds only those. Any other relative include, and `$readmemh`/`$readmemb`/`$fopen`-style
reads during elaboration, refuse the run (`unresolved file dependencies`). Computed includes, line
continuations, token pasting and `__FILE__` refuse before any tool runs. Generated properties
also refuse preprocessor directives and macros, so a plan expression cannot add a live include.
The snapshot may capture inactive literal includes; they must also exist and stay unchanged.

**Evidence and apply.** Schema `rvw.coverage-exclusions/7` keeps each listed file (sources and
harness as written in the plan, plan and database as given) in `files` and each included file in
`dependencies` as a resolution record: the path as opened, every symbolic link met on the lookup
(directories included, `[link, target]`), the resolved path and the SHA-256 of its contents. It also
records the hashed `config`, `work_dir`, `timeout`, the hashed `elaboration` snapshot, the
`source_snapshot` manifest path and hash, `snapshot_sha256` for each point and job, and
`input_hashes` (the RTL and harness copies) for each front end. Apply reads these local artifacts
without running tools. It:

- looks each path up again and rejects a changed link, resolved path or content (pointing
  `defs.svh` at another header with the same bytes is stale too);
- checks the point universe, binds each excluded point's coverage source to a proof input, and
  requires zero hits;
- verifies the raw and rewritten snapshot and the front-end copies, and rechecks the saved raw
  netlist for unsupported state controls;
- rebuilds the sanity cover, point properties, cover isolation script and SBY jobs from the plan
  (plan order fixes the job index and purpose), and recomputes each excluded point's cone.

So an edited point id, expression, reason, assumption, cone or job path cannot move an exclusion
to another point. These checks also apply to files that exclude no points. `report --exclusions`
rejects schemas older than `/7`, and `/7` files made before cover isolation or without the shared
capture record; rerun the proof. Keep the proof directory and inputs beside the database.
Exclusions are local evidence, not portable certificates.

**Limits.** The expression-to-point mapping is reviewed input, not automatic semantic or cone
extraction. Proofs are conditional on the hashed harness's assumptions and reset/initial-state
model. The guards do not prove that the environment is complete: assumptions can still be too
strong in ways the covers do not see. Existing source assumptions can be vacuous; review them.
This tool does not compute solver proof cores, functional cone coverage or automatic cut points, and
it does not prove physical hardware behavior.

## Proof dependency reports

`cov prove` also writes `proof-cones.json` and embeds the same report under
`proof_cones` in its result. See `rvw.proof-cones/1` in
[PLATFORM_CONTRACTS.md](../../../../docs/PLATFORM_CONTRACTS.md).
The report reads the same frozen, flattened Yosys netlist as the proof guards.
For each reviewed expression, it follows all driver inputs, including state,
clock and reset. It includes full named buses. This is a conservative structural
cone. It does not use solver evidence to minimize the cone.

A plan point can add `property_id` and `requirement_ids`:

```json
{"point_id":"p1", "property_id":"counter.range", "requirement_ids":["counter.modulo3"],
 "expression":"s == 2'd3", "reason":"Modulo-3 counter never reaches 3"}
```

`property_id` defaults to `point_id`. It must be unique in the plan. Keep these IDs
stable in requirement and activation records that join this report. This flow
does not measure property activation. It reports `activation.status: not_measured`.
It does not extract a solver proof core. It reports `proof_core.status: unavailable`
and `cells: null`. A successful unbounded job is `proven_conditional`; that label
does not imply that the separate exclusion guards passed.

`outside_proven_cones` lists logic outside all resolved cones of proven properties.
These are candidates for further verification. They are not proven irrelevant.
`untested_assumptions` lists elaborated assumptions with `not_tested` status.
The structural cone excludes assumptions as constraints. It does not establish
their adequacy. A large cone gives no functional coverage percentage.

The native test proves a modulo-3 counter range property. Its known cone includes
the counter addition and state cell. A second graph test checks a two-cell cone,
an unrelated cell, requirement IDs, and an untested assumption.

## Mutation testing

```sh
scripts/with-lock.sh boom rvw/.venv/bin/rvw cov mutate /path/to/mcy-project \
  --run --baseline /path/to/mcy-project/check-original.sh --jobs 1 --timeout 120 --out mutation.json --json
rvw/.venv/bin/rvw cov mutate /path/to/mcy-project --json
```

To earn kills or equivalence, create `rvw-external-inputs` inside the project before the run.
Use a JSON list of every input outside the project. Paths can name files or directories.
Resolve relative paths from the project directory. For example:

```json
["../testbench", "/path/to/shared/options.svh"]
```

Write `[]` if the project has no external inputs. This is an explicit assertion that the input
list is complete. The assertion is captured with the project. Later changes to the live
declaration cannot change that run. With a declaration, a fresh run writes schema
`rvw.mutation/2`. Before it classifies any outcome, it checks the captured declaration, the
capture record and the recorded tool identities. The result records `dependency_complete: true`
and `dependency_declaration.claim` as `"declared complete by the user"`. A fresh run without a
declaration stays `rvw.mutation/1` and is inconclusive (see below).

Use ordinary MCY `config.mcy` to choose module (`select`), mutation count, deterministic seed,
test set and optional equivalence test. The baseline script must be inside the project.
Before the baseline runs, shared `Capture.tree(git=False)` copies the whole project. This
includes untracked and ignored files, nested testbench headers, scripts and symlink targets.
Declared external files and directories also use shared captures. The execution directory
mirrors their original layout so relative paths still find the copies. Literal absolute paths
in UTF-8 input text are redirected to the copies. The result records hashes of the relocated
execution inputs separately from the raw captures. Overlapping declarations refuse capture.
Relative declarations start at the captured project's resolved directory. Declared directory
symlinks retain their execution layout with captured target bytes. Only leading `..` components
are supported in declarations. A later `..` refuses capture because it can cross a symlink.
Baseline, MCY initialization, controls and mutants run in one private project copy.
MCY-listed source bytes must match the capture. Changes to original project files after
capture do not affect this copy. Changes to the execution copy's original input files refuse
the report. Jobs have bounded time and use at most four workers.

The copy is not a sandbox. A cheap scan refuses undeclared literal absolute paths in captured
UTF-8 text, except interpreter shebangs, device streams and pinned tools. In `.v`, `.sv`, `.vh`
and `.svh` files, it scans quoted strings, including literal `include` and `$readmemh`/`$readmemb`
paths. It skips HDL comments and arithmetic operators. Other text still uses the full text scan.
Shell scripts can use literal absolute `mktemp` templates, known compiler `-o`/`--output`
arguments and truncating `>` redirections. These destinations and their later references in
the same script use private scratch. Reads before creation still need capture. Append `>>`
and read/write `<>` redirections do not establish outputs. Unknown tools and unsupported
`mktemp` directory or prefix options keep the input check. Quoted text and comments do not
establish outputs. Existing captured input files retain their execution-copy checks.
Scripts must use relative paths or literal absolute paths for declared inputs. Computed absolute
input paths and binary-embedded paths cannot be redirected. Rewrite those reads before declaring
completeness. Network reads and hidden tool dependencies are not discovered.
The user must review scripts, their tools and their input list. Runtime tools and their installed
support files remain part of the local tool installation. This scan does not prove completeness.

Without `rvw-external-inputs`, dependencies remain unknown. Fresh runs then return
`status: inconclusive`, cause `input_not_captured:mcy_dependencies`, and exit 3.
Stderr gives the declaration filename and format.
Their `counts.killed`, `counts.equivalent`, `counts.survived` and `counts.control` are zero.
`observed_counts` and each row's `observed_state` retain MCY's observations for inspection.
These observations do not establish earned kills or equivalence. No passing cache key is made.

Execution requires a fresh project with no `database/`, `rvw-results/`,
`rvw-mcy-inputs.json` or `rvw-mcy-config.sha256`. Existing and interrupted runs cannot resume.
Use a new project directory to rerun. No automatic purge occurs.
`rvw-mcy-inputs.json` records the declaration, captured inputs, known tools and completeness flag.
Cache keys remain disabled. An explicit declaration does not authorize resume.
Results, logs and the execution project are published through shared result generations under
`rvw-results/`. Omit `--run` to read a pinned generation or a legacy MCY database.
If baseline validation or MCY initialization fails, the error includes the last 4096 bytes
of that stage's log. Failed staging is removed. The error does not link to that removed log.
Inspection of a pinned `rvw.mutation/2` generation with `dependency_complete: true` keeps its
earned results and applies the selected tests again. Every `rvw.mutation/1` result, every `/2`
result without that flag and every raw MCY `database/` is observations only:
`status: inconclusive`, cause `input_not_captured:mcy_dependencies`, exit 3 and zero earned
counts. This includes `/1` results that record `dependency_complete: true`, because older writers
set that flag without complete capture evidence. Existing `/1` files are not relabeled.
`observed_counts` and `observed_state` keep the historical observations. Adding a declaration to
an old project cannot establish its past execution inputs; rerun in a fresh project. CLI and MCP
use the same classification.
A live SQLite WAL or journal refuses capture; stop the writer and checkpoint first.

The observed `mutate -mode none` control is counted separately from actual mutations. With an MCY
equivalence test, pass its name through `--equivalence-test eq` and choose detection tests via
`--test sim` (repeatable). All selected equivalence checks must return PASS to record an observed equivalent survivor.
Missing checks stay pending. Conflicting PASS and FAIL results are errors; equivalence
FAIL is never treated as detection. On a fresh run, omitted options select all tests for detection.
On inspection, each omitted option uses its saved campaign role. An explicit option changes only
that role. The Python API and MCP accept an empty equivalence list to clear that role.
Inspection never writes the changed roles back to the campaign. A saved generation without
both recorded roles stays inconclusive with `input_not_captured:mcy_test_roles`.
Reports record `detection_tests` and `equivalence_tests`. A null `detection_tests` value selects
all non-equivalence tests. Run reports include every selected test in the `replay` command.
To execute that command again, change its project and baseline paths to a fresh project copy.
Survivors may be equivalent or expose real test gaps. They are not classified without a separate
equivalence test. The demo intentionally runs only low input values on one branch, leaving
survivors for inspection. Compilation/infrastructure failures abort MCY rather than killing
mutants. Heavy mutation runs must use the machine-wide lock.

## Verification

```sh
rvw/.venv/bin/pytest -q rvw/tests/cov
source ../spinal-boom/env.sh
scripts/with-lock.sh boom rvw/.venv/bin/python rvw/examples/coverage/demo.py \
  --out "$PWD/.build-logs/coverage-demo-new"
```

The demo builds/runs real Verilator code twice, checks merge counts against `verilator_coverage`,
proves and excludes a real unreachable counter branch with SBY, then runs 24 MCY mutations
against an Icarus testbench after verifying the original baseline. It requires a fresh directory,
keeps all logs/artifacts there, and writes a compact `summary.json`. The proof plan says
`"reset": null` because `tiny` has no reset; without it the vacuity guard refuses. Last full run
(2026-10-22): sanity cover reached, the branch excluded (cover FAIL, prove PASS),
MCY 10 killed, 13 survived, 1 control, none pending or in error. Functional coverage and
source selection tests use explicit C2/Scala fixtures; they are separate from this real-tool demo.
On 2026-10-23, the mutation step was run again with a captured `rvw-external-inputs` containing
`[]`. It reported the same 10 kills, 13 survivors and 1 control as conclusive outcomes.
The existing full demo leaves the declaration absent and keeps its inconclusive observations.
To run only the example mutation step with the explicit assertion:

```sh
mkdir /path/to/fresh-mcy
cp rvw/examples/coverage/{tiny.sv,tb.sv,config.mcy,test_sim.sh,baseline.sh} /path/to/fresh-mcy/
printf '[]\n' > /path/to/fresh-mcy/rvw-external-inputs
rvw/.venv/bin/rvw cov mutate /path/to/fresh-mcy --run \
  --baseline /path/to/fresh-mcy/baseline.sh --jobs 1 --timeout 120 --json
```

The `examples/coverage/spinal/` demo generates a real SpinalHDL 1.15.0 counter/mux with line
comments and runs it through Verilator. Its 44 points include six attributed through actual
statement-span comments; the unreachable assignment maps to `CoverageTiny.scala:14` with
zero hits. The remaining 38 points have no suitable comments and stay unmapped. Reproduce:

```sh
cd rvw/examples/coverage/spinal
sbt -J-Xmx2g -J-XX:ActiveProcessorCount=2 -batch \
  "runMain EmitCoverageTiny $PWD/../../../../.build-logs/spinal-coverage/rtl"
cd ../../../..
verilator --cc --exe --build -j 2 --coverage -Wno-fatal --top-module CoverageTiny \
  --Mdir .build-logs/spinal-coverage/obj .build-logs/spinal-coverage/rtl/CoverageTiny.v \
  "$PWD/rvw/examples/coverage/spinal/sim.cpp"
.build-logs/spinal-coverage/obj/VCoverageTiny .build-logs/spinal-coverage/coverage.dat
rvw/.venv/bin/rvw cov merge spinal=.build-logs/spinal-coverage/coverage.dat \
  --scala-root rvw/examples/coverage/spinal/src/main/scala --out .build-logs/spinal-coverage/coverage.json
```

`check-decode.py` independently compared this decoder with GNU objdump `-M no-aliases` on
the 67 real integer test ELFs: 3,780 unique encodings, zero mnemonic mismatches. This is static
disassembly agreement, not executed instruction coverage. Reproduce with:

```sh
rvw/.venv/bin/python rvw/examples/coverage/check-decode.py --json \
  "${RISCV_TESTS:?Set RISCV_TESTS}"/rv64ui-p-* \
  "$RISCV_TESTS"/rv64um-p-*
```

Non-ELF `.dump` files are skipped explicitly. The check records ELF hashes. `integer-plan.json` is an example declarative
RV64IM instruction by U/S/M mode plan for generating mnemonic holes on the integer suite.
The real `rv64ui-p-add` trace includes both U-mode test code and M-mode setup; mode is read
from each instruction rather than assumed from the test environment's name.

### BOOM collection

Set `SPINAL_BOOM` to a separate BOOM source checkout. Set `RISCV_TESTS` to the
built ISA test directory. Run from the repository root:

```sh
source ../spinal-boom/env.sh
export SPINAL_BOOM=/path/to/your/boom-checkout
export RISCV_TESTS=/path/to/riscv-tests/build/isa
bash rvw/examples/coverage/collect-boom.sh "$PWD/.build-logs/boom-coverage"
```

The example suite discovers all 67 installed `rv64ui-p-*` and `rv64um-p-*` ELFs and requests
coverage plus C2 RVFI traces on `small`. It includes `ma_data`, preserving its status rather
than silently changing the requested test set. The script holds the shared lock, uses one
simulation job, limits JVM processor discovery to four, and retains generated RTL workspaces
for source attribution. The example config disables the runner's nested lock because the script
already owns it. Use `RVW_BOOM_ADAPTER` to choose another checked-out adapter explicitly.
The shared simulation config enables Spinal assignment line comments when coverage is requested.
The installed Verilator 5.049 aborts in experimental FSM detection on a BOOM empty reset
branch (`V3FsmDetect.cpp:641`). The adapter asks Verilator for explicit coverage kinds through `RISCVSIM_COVERAGE`
instead of `--coverage`. Line coverage includes branches. The collector uses the adapter
version gate by default. Set `RISCVSIM_COVERAGE=line,user` to reproduce the historical universe.
Toggle and expression coverage can be added (`line,user,toggle,expr`), at about 230 MB of
`coverage.dat` per BOOM small run for toggle. Each C1 model records `coverage_types`, and its
replay preserves the setting. This is a compiler workaround, not an RTL or coverage exclusion;
native FSM coverage remains unavailable on 5.049. RiscvSim now enables FSM coverage by default
when the native `verilator -V` reports 5.052 or later. It refuses an explicit FSM request on
older or unknown versions. `RISCVSIM_COVERAGE=line,user` still selects the historical point universe.
Do not merge runs from different coverage-kind sets.
Merge each generated C3 `results.json` with `cov merge`, then report/rank the merged database;
feed the runs' `rvfi.jsonl` artifacts to `cov functional`. Keep collection failures visible.

For the full million-point suite, this example runs the same APIs in one process to avoid
reloading the point database for each report. It cross-checks **every merged count** with
`verilator_coverage`, writes a compact `code.json`, and emits `report.json`, `rank.json`,
`functional.json` and `summary.json`:

```sh
scripts/with-lock.sh boom rvw/.venv/bin/python rvw/examples/coverage/report-boom.py \
  .build-logs/boom-coverage/integer-coverage/small/results.json \
  --out .build-logs/boom-report-new --json
```

A prior BOOM `small` integer-suite measurement hit 71.57% of 1,344,229
points. Only 44,135 points mapped to Scala locations; no BOOM points were
excluded by proof. These measurements do not set an acceptance threshold.

## Remaining gaps

Native FSM coverage needs Verilator >= 5.052. Whole-core Scala attribution needs
more HGLDD coverage, particularly declarations and memories. Collapsed Verilator hierarchy
cannot provide exact per-instance counts from these artifacts. Proof exclusions require reviewed
expression mappings. Structural dependency reports do not provide minimal solver proof cores
or property activation evidence. The BOOM RocketALU mutation recipe is in
`examples/boom/mutation-alu/`. It uses a bounded ADD/SUB testbench, not riscv-tests.

## Decisions

Shared formats and the threat model are in `docs/PLATFORM_CONTRACTS.md` (C7, C8 and
"Mutation input declarations"). The sections above state the supported inputs and refusal rules.

- Report only earned results. Missing or ambiguous evidence gives `inconclusive` (exit 3),
  a refusal or an error.
- Read command inputs through C8 captures. Tree limits are 256 MiB and 100000 entries.
  Keep captured identity separate from hashes of generated files. Cache keys stay disabled.
- Record executable identity. MCY has no successful `--version` interface, so record its
  resolved path and captured hash. Proof uses the formal tool bindings and saved environment.
- MCP proof and mutation jobs use `$RVW_HEAVY_LOCK`, default `boom`. `lock: ""` disables it
  for small designs. MCP calculation errors fail the job.
- Publish annotation exports as sealed generations. Check tools and counts before `.dat`
  publication. Use the atomic writer for single JSON exports.
- Merge only equal point universes. Refuse inconclusive runs. Pin one generation per store
  for C3, C1 and coverage bytes. Explicit generation paths keep their selected ID.
- Keep missing source and hierarchy attribution missing. Label assignment-comment and HGLDD
  methods separately. `--scala-root` resolves only unique bare filenames.
- Selection needs a mapped hit for every changed BASE line. Missing evidence or an
  inconclusive run selects all tests. Only `BASE..BASE` selects nothing. Pin each Git ref once.
- Greedy selection includes pruning. Bound `--exact` to 20 tests. The BOOM example requests
  explicit coverage kinds without FSM coverage on Verilator 5.049 and keeps every ELF.
- Functional coverage uses the shared decoder. Reserved encodings are `unknown`. Read FP
  destinations from the encoding. Contradictory traces and unknown alignment are `undetermined`.
- Proof guards read Yosys netlists. Refuse unmodelled behavior, asynchronous state controls,
  latches and clocks outside the single rising-edge clock model.
- Exclusions require an unbounded proof, a reachable sanity cover and a cover showing that
  every state bit read by the point changes. Isolate generated covers; keep source assumptions
  and assertions. Expression mappings and harness assumptions remain reviewed inputs.
- Capture RTL and literal includes before any front end. Every job reads one frozen snapshot.
  Accept only exclusions schema `/7`. Apply checks staleness, evidence, point hits and the
  binding of each excluded point's coverage source to a proof input. Keep the local proof files.
- Use the documented ASCII allow-list for script paths and names. Basenames must be unique
  and start with a letter, digit or underscore. Only `proof.py` writes Yosys and SBY scripts.
- MCY owns mutation generation and scheduling. A fresh `/2` writer checks declaration,
  capture and tool evidence before classification. Every `/1` result and raw database is
  observations only. Do not relabel historical evidence.
- Every selected mutation test needs a passing unmutated control. Failed or missing controls,
  incomplete dependencies and a nonzero MCY exit cannot earn kills or equivalence.
- Mutation execution needs a fresh project, with no resume or cache. Inspection uses saved
  test roles unless overridden for that report. An equivalence FAIL is never a detection kill.
- The mutation literal-path scan is limited. Recognized outputs use private scratch; sed and
  grep patterns are data. Input completeness remains the user's declared claim.

Tool references: [Verilator coverage](https://verilator.org/guide/latest/exe_verilator_coverage.html),
[SBY modes](https://yosyshq.readthedocs.io/projects/sby/en/latest/reference.html),
[MCY configuration](https://yosyshq.readthedocs.io/projects/mcy/en/latest/config.html).

## MCP tools

`rvw mcp` exposes `cov_merge`, `cov_report`, `cov_rank`, `cov_select`, `cov_functional`,
`cov_prove`, and `cov_mutate`. Merge accepts the CLI's `inputs` array, source mapping options,
and optional `out`/`dat`; save `out` as the database for report/rank/select. Functional accepts
`traces`, an optional declarative `config` and an optional `platform`. Arguments use underscores, for example
`source_root`, `work_dir`, `equivalence_test`.

All run as cancellable jobs because databases and traces can be large. Follow them with
`job_status(wait_s=60)` and `job_log`; the final result is the CLI JSON from the same Python
calculation. A failed calculation (missing database, bad diff range, ...) fails the job with
the error message (`job_status` reports `failed`), as C7 requires; the CLI prints the same
message as an `rvw.coverage-error/1` object and exits 2.
Report/rank/select/functional are read-only and return JSON directly; the CLI's
optional `--out` and report `--annotate` exports remain CLI options. Merge, proof and mutation
can write artifacts. Proof/mutation jobs run under `scripts/with-lock.sh LOCK`, where LOCK is the
machine heavy-job lock: `$RVW_HEAVY_LOCK`, else the platform default (`boom`, see
`docs/PLATFORM_CONTRACTS.md`, Resources); a `lock` argument overrides it per call and an empty
value runs without a lock (small designs). Mutation
requires `run=true` and `baseline` to execute MCY rather than inspect existing outcomes.
Proof exclusions and mutation survivors retain the evidence limits documented above.

## Limit ownership

FSM and Scala attribution: [#42](https://github.com/riscPrint/risc-v-workstation/issues/42). Expected ISA bins: [#82](https://github.com/riscPrint/risc-v-workstation/issues/82). Typed RTL events: [#88](https://github.com/riscPrint/risc-v-workstation/issues/88). Temporal coverage: [#115](https://github.com/riscPrint/risc-v-workstation/issues/115). BOOM mutation review: [#3](https://github.com/riscPrint/risc-v-workstation/issues/3). Proof-core reports: [#62](https://github.com/riscPrint/risc-v-workstation/issues/62).

Retained limit: Reviewed expression mappings are not automatic semantic proofs. Capture bounds, unsupported state refusals, reset assumptions and proof/mutation evidence limits remain required. No complete coverage claim follows from observed bins.

### ISA declarations

`rvw cov isa-check isa.json --json` validates a core-owned `rvw.isa/1`
manifest. Declare `isa`, `extensions` (each has `version` and optional
`requires`), `options`, and optional `consumers` (tool name to ISA string).
Use an expanded unversioned ISA string. Use null for an unverified version.
The command rejects missing dependencies and contradictory consumer strings.
Null versions give `inconclusive`. Consumer strings are declarations. Configure
consumer probes below to check actual target macros or consumer settings.

### Pinned opcode bins

Clone `https://github.com/riscv/riscv-opcodes` and check out the `source.revision`
in `examples/boom/isa.json` or `examples/vexriscv/isa.json`. Then run:

```
rvw cov functional TRACE --manifest examples/boom/isa.json --source-root OPCODES --json
```

The manifest pins each selected file by SHA-256. A changed file is an error.
The plan generates every selected canonical opcode and its encoded register
fields. It also generates static rounding-mode fields where present. Each
unobserved bin remains a hole. Trapped records and ambiguous encoding matches
receive no instruction hit. The trace ISA must equal the manifest ISA.
The plan and pins enter the report fingerprint and prevent incompatible merges.
`unavailable` lists excluded scope. Compressed instructions, semantic immediate
classes, operand values, CSR legality, privilege and exceptions are not complete
in this increment. These require semantic data beyond opcode masks. Register
fields are encoded indices, including FP indices; they are not FP data values.
These reports measure selected encoding coverage. They are not compliance results.

### Retirement sequences

Add `"sequences": {"distances": [1, 2, 4]}` to a functional JSON plan. The
command generates fixed bins for RAW, WAW, WAR, branch-after-load, and all
load/store pairs at each distance. Distance counts consecutive C2 instruction
records, not cycles. x0 is not a producer. Register banks stay separate.
A trap, handler entry, unknown instruction or missing order resets the window.
Each file starts a fresh window. Memory pairs describe retirement order, not
address aliasing or memory visibility. Branch-after-load does not require a
register dependency; RAW records that condition separately. These bins cannot
measure forwarding, stalls, speculative execution, flushes or wrong-path work.
Use RTL coverage for those behaviors. No sequence crosses a missing record.

### Review a proposed spec update

```
rvw cov isa-diff OLD.json NEW.json --old-source-root OLD_OPCODES --source-root NEW_OPCODES --json
```

Each manifest pins its own source files. The command verifies both sets of
hashes. It reports added, removed and changed opcode definitions, changed
versions and options, affected declared consumers, and instruction tests to
review. Changed pins require adoption and return `inconclusive` (exit 3).
The command never updates a pin or model. Optional `specifications` declarations
can hold profile, debug and platform document pins. Their metadata is compared;
their semantic obligations are parsed only when a reviewed catalog is supplied
as described below. Catalog completeness still needs review. An unchanged result is not a compliance verdict.

## Scala mapping and denominators

HGLDD signal mapping follows nested struct and vector expressions. A leaf uses
its own Scala declaration. A container line does not stand in for its fields.
Conflicting declarations for the same module and signal stay unmapped.
This mapping applies to toggle points. It does not attribute a branch to a
signal declaration. Assignment comments and explicit HDL spans still map
statement points. Memory declarations without HGLDD expressions stay unmapped.

`report.scala_mapping` gives the mapped-point numerator and the complete
instrumented-point denominator. The small nested-bundle regression target is
100% of its declared leaf toggle points, with no attribution of its unrelated
branch point. This is a checkable fixture target, not a whole-core target.
`instance_scope` gives each hierarchy bucket's instrumented point count.
A literal hierarchy has an exact denominator for that recorded instance bucket.
A wildcard hierarchy has aggregate counts and a null exact-instance denominator.
Missing hierarchy also gives null. These fields cannot recover physical instance
counts after Verilator merges modules. Scala line groups can overlap because
one point can link to several source lines. Do not sum their denominators.

FSM compatibility and Scala mapping are separate checks. `--coverage-fsm`
can compile while some points still lack Scala lines. A compilation check does
not establish state or transition hits.


## Typed RTL event samples

`rvw cov rtl SAMPLES.jsonl --config PLAN.json --json` reads exact-instance
RTL samples. MCP exposes the same calculation as `cov_rtl`. This path is
separate from C2 retirement coverage. It samples internal or interface signals.
Projects supply the plan and sampler. Spinal annotation exporters can emit the
same plan. No native Spinal annotation exporter is included yet.

The plan uses schema `rvw.rtl-plan/1`. `design` identifies the instrumented RTL
and configuration. Use a content hash, not a display name. `signals` maps
exact hierarchical paths to `width`, `type` and `scala`. A Scala link has
`file` and `line`. Use null when no source link is available. Types are
source labels, with an unsigned integer sampling representation. Predicates
map signal names to finite lists of integer values. Their entries form an AND.
Use multiple bins for OR. No expression evaluation or automatic bins occur.

`clock` has `signal`, `edge: rising` and `sampling: pre-edge`.
`reset` has `signal`, `active: 0|1` and `rule: disable-clear`.
The sampler must emit values immediately before every rising edge. The sampled
clock value must be zero. Reset samples disable bins and clear transition
history. Asynchronous reset events between samples are not supported. Refuse
such a sampling model rather than silently treating it as synchronous.

Each bin has a stable `id`, `kind`, `domain` and `when` predicate.
Kinds are `event`, `occupancy`, `state`, `transition` and `arbitration`.
Domains are `structural`, `committed` and `speculative`. Transition bins also
have a `from` predicate for the preceding enabled sample. Ordinary bins count
matching cycles. Transition bins count matching adjacent sample pairs.
The plan lists the whole supported bin universe. Zero-hit bins stay unobserved.
Their reachability is undetermined. This sampler accepts no proof exclusions
and cannot mark a bin unreachable. A covered bin is an observation, not proof.

The first JSONL record has `schema: rvw.rtl-samples/1`, `plan_id` and `design`.
Compute `plan_id` with `rvw.cov.rtl.identity(plan)`: SHA-256 of sorted compact
JSON. Each sample has `cycle` and `values`. Cycles must be consecutive.
Values must contain every declared signal with an in-range integer value.
Unknown values, missing signals and gaps refuse the calculation. The last
record has `event: end` and `complete: true|false`. Missing or false completion
makes the report inconclusive (exit 3), while preserving observations.
The sampler owns this completeness assertion. The reader cannot prove that the
producer sampled the declared edge or observed every cycle.

Supply several sample files to sum independent runs. Each header must match
the exact plan hash and design. Transition history never crosses runs.
Duplicate trace bytes refuse counting. Saved reports are not merge inputs.
The bin merge key is `(plan_id, id)`. Changing a domain, source link, clock,
reset rule or bin universe changes the plan hash. `rvw.rtl-coverage/1` reports
the declared denominator, observed bins, per-bin counts, event domains and
reachability separately. Input captures retain plan and sample hashes.


## Bounded RTL sequences

A plan can add `sequences`. Each sequence has a unique `id`, a `domain` and
2 to 32 `steps`. The first step has `when`. Each later step has `when` and
`delay: [minimum, maximum]`. Delays count rising-edge samples from the preceding
matched step. Both limits are inclusive integers from 1 to 1000000.
Zero-delay, unbounded, falling-edge and multi-clock semantics are refused.

A first-step match activates one attempt on each matching cycle. Attempts can
overlap. Each attempt advances on the first match in its delay window and can
complete once. This is deterministic first-match sequence coverage, not SVA
assertion semantics or all possible path enumeration. Reset cancels pending
attempts. Runs never share attempts. An attempt expires on the first sample
after its last allowed delay. Attempts still open at trace end stay pending.
The report keeps `activated`, `completed`, `expired`, `reset_cancelled` and
`pending` separate. Pending attempts are not failures or unreachable bins.
Their sum satisfies activated = completed + expired + reset_cancelled + pending.

Run the native small example from the repository root:

```sh
scripts/with-lock.sh vex nice -n 10 rvw/.venv/bin/python \
  rvw/examples/coverage/rtl/demo.py /tmp/fresh-rtl-coverage
rvw/.venv/bin/rvw cov rtl /tmp/fresh-rtl-coverage/samples.jsonl \
  --config /tmp/fresh-rtl-coverage/plan.json --json
```

The example builds a small FSM with Verilator 5.052 or later. It collects
pre-edge samples of actual state values and native FSM and line coverage.
It declares all four state codes and one idle-to-active transition. State 3
stays unobserved with undetermined reachability. A bounded round trip records
activations and completions. Its source is SystemVerilog, so Scala links are
null. The output directory must be new. Build logs and measurements stay there.

### Semantic bins and closure candidates

A pinned `rvw.isa/1` manifest can enable semantic bins:

```json
"semantics": {
  "version": 1,
  "privilege_modes": ["M", "S", "U"],
  "exceptions": {"ecall": [8, 9, 11], "lw": [4, 5, 13]}
}
```

The exception list is a project declaration of expected crosses. Review it
against the pinned specification and implementation options. The tool does not
infer that every listed cross is reachable. An omitted cross is outside this
plan. It is not proven unreachable. The manifest is part of the plan hash.

Integer `rs1` and `rs2` value classes are zero, one, all ones, signed minimum,
signed maximum, other positive, and other negative. These bins use RVFI operand
data. Missing data earns no hit. FP source files do not use integer RVFI data.
The first semantic version supports base I, M and Zicsr source files. It also
covers encoded `imm12` boundary classes and legal CSR read/write access kinds.
Other immediate formats and compressed semantic forms remain outside this plan.
CSR access bins describe the encoded access request. They do not prove a CSR
side effect. Trapping instructions earn no successful instruction or access hit.

Per-instruction exception hits require a decoded `trap=true` instruction followed
by a synchronous C2 trap event at the same cycle. Missing or late cause evidence
earns no per-instruction exception hit. Privilege transitions use adjacent RVFI
instruction modes. Order gaps reset the window. They do not measure pipeline
speculation or the exact trap-entry cycle.

`sequences.kinds` can select RAW, WAW, WAR, branch-after-load, the four load/store
pairs, and branch/jump control-flow pairs. `sequences.distances` selects retirement
distances. Traps, handler entry, order gaps and unknown instructions reset the
window. These pairs do not establish timing hazards or memory visibility.

Create a project-owned candidate file:

```json
{"schema":"rvw.coverage-candidates/1","tests":[
  {"id":"integer-boundaries","targets":["sem_add*"],"priority":10,
   "reason":"Exercises zero, sign boundaries and all ones"}
]}
```

Run `rvw cov closure coverage.json --candidates candidates.json --json`.
The input can be a functional report, an RTL report, or a code coverage database.
The report lists each unhit bin. It ranks matching test suggestions by descending
project priority and then test ID. Targets use shell glob syntax over bin IDs.
Functional IDs use `GROUP:JSON_ARRAY`, without spaces in the array.
The report hashes both input files. Suggestions are not measured hits. A bin with
no matching candidate keeps an empty list. Exclusion and reachability remain
separate fields. Code exclusions retain their input envelope and do not gain a
new reachability claim from this command.

### Exact instance collection and declaration attribution

RiscvSim coverage builds use `--coverage-per-instance` with the checked native
Verilator version 5.052 or newer. Older or unknown tools retain collapsed coverage. Recollect old
collapsed data to get exact instance denominators. A wildcard hierarchy still
has no exact denominator. Denominators count instrumented native points, not
all possible hardware events or all Scala source lines.

`rvw cov merge TEST=coverage.dat --hgldd design.dd --design-db design.db --json`
can add declarations from the same SpinalDB elaboration. The database must use
`rvw.designdb/20`. Each covered RTL file must match its captured hash. Assignment
and declaration targets within a native covered span map to exact-instance
signal and memory declaration locations. This is declaration attribution. It
is not a claim that the Scala declaration is the source of each RTL branch.
HGLDD exact-instance overrides resolve deduplicated signal declarations.
Conflicting module-only declarations remain unmapped. The tool does not choose
a nearby comment or expand a collapsed hierarchy.

Use `closure --exclusions proof.json` to validate code-point proof evidence with
the existing proof guard. Only this validated input earns `proven-unreachable`.
An embedded exclusion envelope alone stays `reachability: undetermined`.

For schema `/20`, declaration mapping also reads exact memory symbol names from
`MemSymbolesTag` in captured memory keys. This covers split memory arrays that
have no HGLDD signal expression. Unknown symbol names stay unmapped. The mapper
does not construct a symbol name from a memory-name suffix.

Branch operands can link to their exact-instance declarations within the covered
span. These links do not claim that a declaration is the source statement of the
branch. `method` separates comment links, declaration links, and mixed links.
HGLDD multidimensional Vecs retain each dimension during leaf traversal.
Each instance report includes mapped and unmapped point counts with its denominator.

RTL sequence goals with no completion also appear in the closure report.
Their pending activation count stays separate from reachability.

### Reviewed specification obligations

`isa-diff` can compare semantic obligations for ISA, profile, debug and platform
pins. Each `specifications` entry can declare `kind`, `revision`, `path`,
`sha256`, and `obligations: {"path": "rules.json", "sha256": "..."}`.
Paths use the corresponding source root. The document hash binds the exact
specification bytes. The catalog uses `rvw.spec-obligations/1` with an
`obligations` array. Each row has a unique `id`, exact document excerpt `text`,
`checkers` (names), and `tests` (source-root-relative file paths).

The command checks both hashes and checks each excerpt against its document.
It compares obligations by ID, reports both sides of changed obligations, and
lists added and removed obligations. It checks test file presence and captures
present files by hash. An empty test list is a missing-test entry. Presence is
not a test result. Changes require explicit adoption. No model or pin changes.
Catalogs need human review for completeness. Metadata-only pins appear in
`unchecked_specifications`. This path does not extract every normative rule
from arbitrary prose. It does not establish compliance.

### ISA consumer probes

An optional `probes` object in the manifest selects `compiler`, `dut`,
`reference`, `act` and `coverage` inputs. Each probe has one of these forms:

- `{"kind": "gcc", "argv": ["riscv64-unknown-elf-gcc", "-march=rv32im", "-mabi=ilp32"]}`
  reads native target macros. It adds `-dM -E -x c -` and supplies empty input.
- `{"kind": "json", "path": "adapter.json", "key": ["isa_config"]}`
  reads actual JSON settings. `kind: "toml"` reads TOML settings.
- `{"kind": "command", "argv": ["adapter", "isa-config"]}` reads a native
  capability command. It must return `schema: "rvw.isa-consumer/1"`.

File and command inputs report `xlen`, `extensions` (name to version string
or null), and `options`. Paths use the manifest directory. Commands have a
10-second process-group timeout. The capture records tools and input files.
Probe settings must select the same configuration used by the consumer.
The check rejects contradictory XLEN, extension sets, known versions and
options. M permits the implied Zmmul subset in GCC output. Missing probes,
unknown versions and missing option evidence give `inconclusive`. Only all
five consistent inputs give `consistent`. This is a configuration check, not
an ISA compliance result. A capability command is a consumer report, not an
independent proof that the consumer implements that version. Existing adapters
without capability commands still need an integration or a settings-file probe.

### Reviewed semantic forms and crosses

`semantics.forms` can declare bit layouts for each pinned instruction name.
This supports compressed forms and split immediate layouts without guessing
from mnemonic spelling. Each form maps field names to `bits`, `width`, `bins`,
and optional `signed`, `offset` and `bank` (`integer|float`). A bit slice is
`[instruction_high_bit, instruction_low_bit, result_low_bit]`. The reader joins
slices, applies sign extension, then adds the offset. For example:

```json
{"c.addi": {"imm": {"bits": [[12,12,5], [6,2,0]], "width": 6,
                       "signed": true, "bins": "boundaries"},
             "rd": {"bits": [[11,7,0]], "width": 5,
                    "bins": [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,
                             16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31]}}}
```

`boundaries` creates zero, positive, negative, minimum and maximum classes.
A zero bit omitted from a slice stays zero. Compact registers can use offset 8.
Fields named `rs1|rs2` with `bank: "integer"` also generate operand-value bins.
Missing RVFI operand values earn no hit. Floating fields do not use integer data.

`semantics.crosses` is an array of `id`, `instruction`, `fields` and
`combinations`. Each combination has `bin`, `status` (`legal|illegal|unavailable`)
and `reason`. Every Cartesian combination of the declared field domains must
have exactly one classification. The reader refuses incomplete catalogs.
Reports retain all combinations in the denominator and report observations per
classification. A declared illegal or unavailable bin is not a proof exclusion.
These declarations require spec review. The tool does not claim that a finite
catalog covers every semantic obligation of the selected ISA version.

### Assignment navigation from the same-elaboration database

When a covered native line names an assignment target, the mapper can link it
to a unique full data assignment in the same instance. It uses the database
assignment location instead of the signal declaration. Multiple assignments,
reset/init assignments, partial targets and parent-to-child assignments refuse
this inference. Wildcard instances and toggle points do not get assignment
links. The mapper still checks the RTL hash against the database capture.
The method is `covered-span-assignment-links`, or a mixed variant when the
point also has other source links. These are navigation links. A native point
can cover several emitted statements. It does not prove individual Scala
statement hits. `scala_mapping.methods` reports each mapping method separately.
`statement_hit_status` stays `undetermined`.
