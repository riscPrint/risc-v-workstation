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
This tool does not compute proof cores, cone-of-influence coverage or automatic cut points, and
it does not prove physical hardware behavior.

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
`--test sim` (repeatable). A PASS from equivalence records an observed equivalent survivor; equivalence
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
branch (`V3FsmDetect.cpp:641`). The adapter therefore asks Verilator for explicit coverage
kinds (`RISCVSIM_COVERAGE`, default `line,user`; line coverage includes branches) instead of
`--coverage`, which would include FSM coverage. The collector sets `RISCVSIM_COVERAGE=line,user`.
Toggle and expression coverage can be added (`line,user,toggle,expr`), at about 230 MB of
`coverage.dat` per BOOM small run for toggle. Each C1 model records `coverage_types`, and its
replay preserves the setting. This is a compiler workaround, not an RTL or coverage exclusion;
native FSM coverage remains a gap on this installed tool version.
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

Native FSM coverage is disabled on this installed compiler. Whole-core Scala attribution needs
more HGLDD coverage, particularly declarations and memories. Collapsed Verilator hierarchy
cannot provide exact per-instance counts from these artifacts. Proof exclusions require reviewed
expression mappings and do not compute proof cores; the only cone they trace is the combinational
fan-in of the point for the cone cover. The MCY end-to-end
demonstration is the small design; BOOM-unit mutation with a riscv-tests subset was not run.

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

### ISA declarations

`rvw cov isa-check isa.json --json` validates a core-owned `rvw.isa/1`
manifest. Declare `isa`, `extensions` (each has `version` and optional
`requires`), `options`, and optional `consumers` (tool name to ISA string).
Use an expanded unversioned ISA string. Use null for an unverified version.
The command rejects missing dependencies and contradictory consumer strings.
Null versions give `inconclusive`. Consumer strings are declarations. This
increment does not probe compiler, adapter, reference model or ACT settings.
