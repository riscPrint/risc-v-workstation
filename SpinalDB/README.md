# SpinalDB

The default navigation roots `src/main/scala` and `src/test/scala` are optional.
The capture record lists an absent default root as `state: absent` under
`optional_source_roots`. Roots set through `DbOptions.sourceRoots` or `--source-root`
are required. A missing explicit root makes the capture inconclusive.

One extraction run over a SpinalHDL design (elaborated twice, the second time with source locations) that writes a **design database**: a SQLite file
(schema `rvw.designdb/20`) holding the hierarchy, every signal, register, memory and port, every
assignment with its `when`/`switch` conditions and Scala source line, the dependency graph between
signals, and the Verilog and waveform names of RTL signals. Synchronous read-port state also has
database-only graph nodes. The same elaboration also produces
SpinalTrace's PDG, SpinalBlocks' diagram and SpinalWaves' HGLDD, stored in the database, so those
tools no longer need to elaborate separately.

The database answers the questions an engineer or an agent asks about the hardware without
looking at a diagram (`rvw query`, below): what drives this register and under which condition,
what reads it, what lies between the D-cache response and the register file write port, where is
it in Scala, what is it called in the Verilog and the waveform, what did my Scala edit change in
the elaborated hardware.

## Build a database

Requirements: JDK 21, sbt, Python >= 3.11 and Yosys for BlackBox bodies (`source ../spinal-boom/env.sh`), SpinalHDL 1.15. SpinalDB builds
against `../SpinalWaves`, `../SpinalTrace` (ProjectRef) and `../SpinalBlocks` (its sources).

Any component with a no-argument constructor:

```sh
SpinalDB/build-db.sh class my.pkg.MyTop out/my.db --sbt-dir path/to/project   # project depends on spinaldb
# or, inside SpinalDB/spinaldb (the example designs are on the Test classpath):
cd SpinalDB/spinaldb && sbt "Test/runMain spinaldb.Main spinaltrace.examples.GCD gcd.db --source-root ../../SpinalTrace/examples/src"
```

From Scala, for components that take parameters:

```scala
spinaldb.SpinalDB.generate(SpinalConfig(targetDirectory = "rtl"), new java.io.File("my.db"))(new MyTop(cfg))
```

A named entry is a directory `SpinalDB/<entry>/` with its own sbt build, whose `run CONFIG OUT
[options]` writes the database, and an `entry.sh` that `build-db.sh` sources for the entry's
environment and the machine lock it holds (`LOCK`). The design-specific settings live there, not
in the generic scripts. The `boom` entry builds spinal-boom (`small`, `medium`, `large`, `mega`,
`giga`) from `$SPINAL_BOOM` (default: the private clone `../spinal-boom-eda`) and holds the
`boom` lock:

```sh
SpinalDB/build-db.sh boom small SpinalDB/out/boom-small.db
```

`build-db.sh` hands its arguments to the JVM in a NUL-separated file (`--args-file`, read by
`spinaldb.Main.parse`), so paths with spaces, quotes or `;` reach SpinalDB unchanged and never
pass through sbt's command parser. The MCP tool `query_build_db` takes `design` (a class) or
`entry` plus `config`.

Options (all entry points): `--rtl DIR` (where the Verilog goes), `--source-root DIR` (repeatable;
where Scala file names are resolved, default `src/main/scala` and `src/test/scala`), `--no-pdg`
(skip SpinalTrace's naming phase and PDG: the Verilog is then exactly a plain build's),
`--pdg-tables` (also store the PDG as tables), `--no-blocks`, `--no-hgldd`, `--meta KEY=VALUE`,
`--blackbox-source DEFINITION=FILE` (repeatable: the external Verilog/VHDL of the BlackBox with
that definition name, hashed into its body fingerprint; see "Allow-list rule" below).

The RTL is generated as usual; the database records where (`meta.rtl_dir`, table `rtl_files`).

### Cost on spinal-boom (`0cb0b69`, Apple M-series, 10 cores shared)

| Config | Wall (sbt start to DB) | Elaboration (2 passes) | Extraction | Peak RSS | DB size | Components | Signals (named) | Registers | Assignments | Edges |
|---|---|---|---|---|---|---|---|---|---|---|
| small  | 43 to 65 s | 19 to 31 s | 13 to 19 s | 4.8 to 5.2 GB | 79.5 MB | 218 | 128 279 (44 038) | 23 270 | 92 283  | 191 552 |
| medium | 66 to 87 s | 39 to 58 s | 20 to 21 s | 6.0 to 7.7 GB | 117 MB  | 248 | 186 377 (62 968) | 32 885 | 144 430 | 313 060 |

The table was measured with schema `/1`. One schema `/2` build of small (2026-10-21, typed keys,
memory init, masks) took 44 s wall, 18.9 s elaboration, 13.8 s extraction (netlist tables 4.6 s),
5.4 GB peak RSS, 86.8 MB on disk and 191 586 edges (+34 write-mask edges); medium was not rebuilt.
A diff of the small database against itself takes 4 s.

Ranges are over several runs on a machine shared with other jobs. Extraction is the netlist tables (6 to 8 s), the PDG (5 s), the diagram (2 to 5 s) and the HGLDD
(3.5 s). Queries on the small database take 0.3 to 0.9 s including Python start-up; a diff of
small against medium takes 5.5 to 6.5 s.

## What is in the database

Every signal of the elaborated design is one row in `signals`, identified by `path`: the instance
path below the toplevel plus the Verilog name (`tile.core.rob_1.rob_head`). That is also the
waveform path under the scopes in `meta.extra_scopes` (`TOP BoomSimTop`) and the symbol used by
SpinalTrace's PDG. `spinal_path` is the typed path through bundles, Vec indexes and Areas
(`tile.core.rob_1.io.enq.valids.0`, `fifo.logic.ptr.push`).

Compiler temporaries (Spinal's `_zz_*`, `when_File_l12` condition wires) are kept, because they
are in the Verilog and the waveform. `_zz_*` wires are flagged `generated`, and so are
`when_<File>_l<N>` and `switch_<File>_l<N>` wires when Spinal gave them that name (`/10`:
`SpinalDB.elaborate` tags a signal whose name has Spinal's `REMOVABLE` priority before Spinal makes
every name strong). A signal the user named like that (`first.setName("when_Test_l12")`) is not
generated: it is compared by its name, and a wire of that kind adds a `warnings` row. Readers skip
internal temporaries by the `generated` flag, never by the name (`/9` and older matched the name, so a user
register named `when_Test_l12` was masked). Signals Spinal pruned (unused or
constant) are kept flagged `pruned`, so a query can say so instead of "not found".
Ports keep their declarations, attributes and tags in `diff`, even with `generated` set.
Incomplete markers on internal signals and their assignments remain undetermined, even when
the signal is generated or pruned.

### Schema `rvw.designdb/20`

Locations use `file_id` and `line`. Signal paths use instance names below the toplevel.
Display expressions use names relative to their component and stop at 400 characters.
Display text can omit casts and resizes. Comparisons use typed `key` columns instead.
Navigation reads schemas `/1` through `/20`. Diff requires `/20` on both sides.
Rebuild older databases before comparing them.

#### Typed keys

Keys include the supported node's class, width, operands and constant parameters.
Strings are escaped. Numbers retain their types. Nested keys and clock-domain fields
are length-framed. Sets and maps are sorted for tag payloads. Emission objects retain
their collection order. Tags and attributes retain Spinal's emission order.
Enum types include element order, encoding width and each encoded value.

Internal compiler temporaries are keyed by their logic. A temporary with several
assignments includes each assignment and its condition in order. Generated registers
use `$reg:<hash>#<rank>` identifiers for their register graph. The rank keeps distinct
registers with equal content distinct. Register cycles use a canonical graph walk.
A cycle with more than 2 000 registers is incomplete. Ports keep external paths,
even when Spinal marks their names generated. User names that resemble generated
names remain named signals.

Clock-domain keys include control paths, reset kind, edge, polarities and the typed
logic of clock, reset, clock-enable and soft-reset signals. Raw register templates
use register tokens until generated-register IDs are ready. Recursive domains are
incomplete. Synchronous memory reads have separate `mem_read` state nodes. These
nodes have no RTL or waveform name.

#### Allow-list rule

An unsupported construct produces `$incomplete:`. A hash that includes an incomplete
part starts with `h!:`. Such keys cannot establish equality. Diff reports affected
paths under `undetermined`. A complete definite change can still establish
`identical: false`; missing capture evidence makes the result inconclusive.

- Expressions require a supported library class and a complete field allow-list.
  Every held expression must occur in the operand walk. New fields in a library
  upgrade make the node incomplete.
- Signal types use the fixed Bool, Bits, UInt, SInt and SpinalEnumCraft allow-list.
  Unsupported signal declarations remain incomplete, including unused generated signals.
  Container override checks are outside the C8 threat model.
- Assignments distinguish `data`, reset `init` and power-on `initial`. Keys retain
  partial targets and assignment order. Switch branches include earlier case keys
  when they can overlap. Defaults include every blocking case, including empty cases.
  Exclusivity requires exact values and preserves the switch width rules.
- Memory keys include size, layout, technology, blackboxing flags, initial contents
  and tags. Memory-port keys include width, enables, mask, read-under-write and
  during-write policies, clock domain and enclosing conditions.
- Assertions, assumptions and covers retain condition, message, severity, trigger
  and clock domain. Unsupported statements remain incomplete.
- Tags and attributes retain payload fields, constant `final val` values, language
  eligibility and elaboration flags. Constant values come from Scala signatures.
  Compiler fields are omitted by exact name, modifiers and type: `MODULE$`,
  `serialVersionUID` and lazy-val bitmaps. Other fields remain payload.
  Case-class fields are read by reflection. An unreadable or unsupported value
  makes the key incomplete. File-valued attributes also include captured file bytes.
- Known library classes retain exact-class and origin checks. Bookkeeping tags
  listed in `Extractor.IgnoredTags` are omitted. Clock-role self references are
  cut at their own domain; other domain cycles are incomplete.
- Effective emission settings are compared for the whole design, including scoped
  comparisons. User emission phases and objects include captured compiled code
  and reflected state. Missing class bytes or unknown state make keys incomplete.

User emission keys cover compiled code and reflected state. Whole-entry and
whole-classpath changes can give conservative differences. Capture is limited to
512 MiB and 100,000 entries per classpath directory. Missing code sources, nested
classpath symlinks, unsupported lambda metadata and cycles remain incomplete.
These keys do not capture arbitrary generator reads of files, environment variables
or mutable global state. See C6 for the supported emission-value contract.

#### BlackBox inputs

BlackBox keys include definition name, generics, libraries, whitebox policy and a
body fingerprint. Capture inline HDL before emission. Capture external roots and
literal includes before Yosys reads them. Both `SYNTHESIS` contexts use private
execution copies. Check preprocessor reads against that capture, apply generics,
and run `hierarchy -check` for the selected definition.

The scan refuses external conditional symbols, macro-built includes, context-changing
directives, runtime file reads and unsupported dependencies. This includes ordinary
include guards and can include harmless directive text in comments. VHDL bodies,
libraries, missing modules, absent Yosys, failed tools and timeouts make the body
incomplete. The scan does not establish another tool's language semantics.
Yosys runs through the resolved launcher recorded by `Capture.tool`. Its path, hash
and observed version identify that launcher. They do not identify every transitive
tool dependency. `verify_tools` still checks the recorded tools.

The Python bridge uses `rvw.common.proc.run_group` for timeout and cancellation of
the full process tree. `SPINALDB_PYTHON` selects Python. `SPINALDB_YOSYS` selects Yosys.
`input_files` and `meta.input_capture` record the captured inputs and problems.
Default source roots can be absent. Explicit source roots must be captured.

Not compared: assignments to pruned signals, simulation-only public flags, naming
options already reflected in paths, and generated Verilog text itself.

| Table | Columns | Meaning |
|---|---|---|
| `meta` | `key`, `value` | `schema`, `generator`, `spinalhdl`, `emission_config` (effective emission settings), `toplevel` (module name), `toplevel_class`, `extra_scopes` (waveform scopes above the toplevel's signals), `created`, `source_roots`, `pdg_naming_phase`, `pdg_tables`, `elaboration_s`, `rtl_dir`; BOOM adds `core`, `config`, `core_repo`, `core_rev`, `core_dirty`; `--meta` adds more (`source_repo`, `source_rev`, `source_dirty` let `rvw query` warn about a stale database, as the `core_*` rows do). |
| `files` | `id`, `path` | Scala source files (absolute when found under a source root, else the bare name). |
| `components` | `id`, `parent_id`, `path`, `name`, `module`, `class_name`, `blackbox`, `depth`, `file_id`, `line`, `tags` | One row per instance. `path` is the instance path (`""` for the toplevel), `module` the Verilog module (deduplicated instances share it), `class_name` the Scala class, `tags` the instance's and the definition's tags and attributes (`instance: ...; definition: ...`, NULL when none). |
| `areas` | `id`, `component_id`, `parent_id`, `name`, `path`, `class_name`, `file_id`, `line` | Named Areas (also FSMs, pipelines) of a component; `path` relative to the component (`logic.ptr`). |
| `bundles` | `id`, `component_id`, `parent_id`, `path`, `class_name`, `direction`, `signals`, `bits`, `file_id`, `line` | Every named composite Data owning signals: Bundle, Vec(n), Stream, Flow, MicroOp... `path` is the full Spinal path (`tile.dcache.io.lsu.req`), `direction` `in`, `out`, `in/out`, `internal` or `mixed`; `signals`/`bits` count the live leaves. These are the interfaces. |
| `clock_domains` | `id`, `clock`, `reset`, `reset_kind`, `reset_active_high`, `clock_enable`, `soft_reset`, `clock_edge`, `clock_enable_active_high`, `soft_reset_active_high`, `clock_key`, `reset_key`, `clock_enable_key`, `soft_reset_key` | Distinct clock domains of registers and memory ports, signals by `path`. Each `*_active_high` is `true`/`false`, NULL when that control is absent. Each `*_key` is the typed key of that control signal from the toplevel (generated wires followed to their logic), NULL when absent; `unpulled:<name>` for a signal no component uses. |
| `signals` | `id`, `component_id`, `area_id`, `name`, `path`, `spinal_path`, `kind`, `direction`, `type`, `width`, `data_type`, `clock_domain_id`, `reset_value`, `clock_role`, `generated`, `pruned`, `tags`, `port_index`, `file_id`, `line` | `name` is the Verilog name in its module. `port_index` is a port's place in its module's port list as Spinal emits it (0 first; `getOrdredNodeIo` without suffix fields such as a Stream's `fire`), NULL for other signals. `kind` is `reg`, `wire`, `mem` or `mem_read` (a memory array and synchronous read-port state take part in the graph). A `mem_read` name and path identify a database-only node, not an RTL or waveform signal. `direction` `in`/`out`/`inout` for ports. `type` `Bool`, `UInt`, `SInt`, `Bits` or `<enum>@<encoding>[<width>]{<element>=<value hex>,...}` (`State@seq[2]{a=0,b=1,c=2}`); `tags` the signal's tags and attributes as text (see the allow-list rule); `data_type` the bundle or Vec directly owning the signal. `reset_value` is the register's `init` (NULL: not reset). `clock_role` marks clock, reset, clock-enable and soft-reset nets. The location is the declaration; a bundle field defined in another file is located where its bundle is declared in this design. |
| `memories` | `id`, `signal_id`, `component_id`, `name`, `path`, `width`, `depth`, `technology`, `init_sha256`, `init_words`, `key`, `file_id`, `line` | One per `Mem`. `init_sha256` hashes the initial contents (ROMs, initialized RAMs; NULL without init), `init_words` counts them. A rejected numeric payload gives an `$incomplete:memory init` marker followed by the digest. `key` holds every behavior field of the `Mem` (see the allow-list rule). |
| `mem_ports` | `id`, `memory_id`, `component_id`, `kind`, `address`, `data`, `enable`, `write_enable`, `mask`, `clock_domain_id`, `cond_id`, `key`, `file_id`, `line`, `output_id` | `kind` is `write`, `read_sync`, `read_async`, `read_write` or `read_async_write`; expressions as text. `key` is the compared form: width, `rw=` read-under-write and `dw=` during-write policy, vital flag, the typed keys of address, data, enable, write enable and mask, and the port's tags; the clock domain and enclosing condition are compared through `clock_domain_id` and `cond_id`. `output_id` links a synchronous port to its `mem_read` signal; NULL for other ports. |
| `statements` | `id`, `component_id`, `kind`, `key`, `clock_domain_id`, `cond_id`, `file_id`, `line` | Statements that are not assignments, conditions or memory ports: `assert` (assertions, assumptions, covers, with their typed key) `declaration` (an unsupported signal class), and `other` (an unmodelled statement; key `$incomplete:`). |
| `blackboxes` | `component_id`, `generics`, `rtl_paths`, `body_sha256`, `body_from`, `key` | One per BlackBox instance (`components.blackbox = 1`): its generics as typed text (`K=Int 2`), its `addRTLPath` files, the SHA-256 of its external body over its dependency set (inline HDL, RTL files, `--blackbox-source` files, every file they include, generics and scan context; NULL when it cannot be determined) and what it covers (`body_from`), and the compared `key` (with the reason when incomplete). |
| `conds` | `id`, `parent_id`, `component_id`, `kind`, `expr`, `keys`, `key`, `signal_id`, `file_id`, `line` | The `when`/`switch` tree. `kind` `when` (true branch), `else` (false branch of the same `when`, same `expr`), `case` (`keys` the case keys) or `default`. `key` is the typed condition: the `when` condition, or the `switch` value with the keys that select the branch (`|k1|k2`, `|not{...}`; see the allow-list rule). `signal_id` is the condition signal when the condition is one. |
| `assignments` | `id`, `target_id`, `component_id`, `kind`, `range`, `source`, `enable`, `mask`, `key`, `cond_id`, `seq`, `file_id`, `line` | Every `:=`, `init` and `initial`, and every memory write. `kind` `data`, `init` (reset value), `initial` (power-on value) or `mem_write`; `range` a partial target (`(3)`, `(7 downto 0)`, `(idx)` for dynamic); `enable` the write enable of memory writes; `mask` the write mask of masked memory writes (also a `cond` dependency of the memory); `key` the typed form of range, source, enable and mask; `cond_id` the innermost enclosing condition; `seq` elaboration order (a later assignment wins when its condition holds); `component_id` where the statement is (a parent drives a child's input). |
| `assign_reads` | `assignment_id`, `signal_id`, `kind` | Signals an assignment's source (and dynamic target index) reads, `data` or `sel`. |
| `cond_reads` | `cond_id`, `signal_id` | Signals a condition reads. |
| `edges` | `src`, `dst`, `kind` | Signal dependency graph: `dst` depends on `src`. `data` (value flows, including both directions of analog net attachments), `cond` (an enclosing when/switch reads it), `sel` (mux select, dynamic index, memory address or enable), `init` (reset value), `blackbox` (each output or inout depends on each other input or inout). Self-edges are kept (`x := x - y`); an opaque inout does not get a self-edge merely from its direction. Edges go through compiler temporaries; `rvw query` makes those transparent. |
| `pdg_vertices`, `pdg_edges` | | SpinalTrace's statement-level PDG as tables, only with `--pdg-tables` (55 MB for BOOM small). |
| `artifacts` | `name`, `media_type`, `encoding`, `size`, `content` | Gzipped outputs of the same elaboration: `pdg.json` (SpinalTrace, docs/PDG_FORMAT.md there), `blocks.json` (SpinalBlocks, docs/FORMAT.md there), `hgldd/<top>.dd` (SpinalWaves, for Surfer). `size` is uncompressed. `rvw query export` writes them out. |
| `input_files` | `path`, `resolved`, `sha256`, `size`, `record` | C8 file capture records. Hashes cover the exact copied bytes. |
| `clock_frequencies` | `clock_domain_id`, `hz` | Declared frequency of a clock domain (Spinal `FixedFrequency`), as a plain decimal in hertz. No row: unknown frequency. Added without a schema bump: older databases lack the table, and readers treat that as unknown. |
| `rtl_files` | `path` | The generated Verilog. |
| `warnings` | `source`, `message` | Things the extraction (`spinaldb`) or the PDG (`pdg`) could not model exactly. |

Example, without rvw:

```sql
-- what drives the ROB head, under which condition, from which line
SELECT a.source, c.kind, c.expr, f.path, a.line FROM assignments a
  JOIN signals s ON s.id = a.target_id LEFT JOIN conds c ON c.id = a.cond_id LEFT JOIN files f ON f.id = a.file_id
 WHERE s.path = 'tile.core.rob_1.next_rob_head' ORDER BY a.seq;
```

## Querying it

`rvw query` (in `rvw/`, see `rvw/src/rvw/query/README.md`) and the MCP server `rvw mcp`
(`rvw/src/rvw/mcp/README.md`). For example, on BOOM small:

```text
$ rvw query drivers lsu.stq_commit_head --db SpinalDB/out/boom-small.db
tile.lsu_1.stq_commit_head reg UInt[4]
  register on clk (RISING), no reset
  := (io_core_commit_valids_0 && io_core_commit_uops_0_uses_stq) ? (stq_commit_head + 1)(3 downto 0) : stq_commit_head
      at .../boom/lsu/lsu.scala:1736 (in tile.lsu_1)
  := 0
      under when(reset || io_core_exception) && when(reset)
      at .../boom/lsu/lsu.scala:1890 (in tile.lsu_1)
```

## Code

| File | What |
|---|---|
| `spinaldb/src/main/scala/spinaldb/SpinalDB.scala` | API: `elaborate`, `write`, `generate`. |
| `spinaldb/src/main/scala/spinaldb/Extractor.scala` | The netlist walk that fills the tables; runs the PDG, diagram and HGLDD extractors on the same report. |
| `spinaldb/src/main/scala/spinaldb/ExprText.scala` | Expression rendering, typed keys and the allow-list check (`ExprText.modelled`, `InfraFields`). |
| `scripts/hdl_capture.py` | Shared C8 capture bridge, literal include copies, pinned Yosys scans and tool checks. |
| `spinaldb/src/main/scala/spinaldb/InlineCapture.scala` | Constant inline bodies captured before emission. |
| `spinaldb/src/main/scala/spinaldb/HdlDeps.scala` | The BlackBox body's dependency set, read by the Yosys front end (needs `yosys` on `PATH`). |
| `spinaldb/src/main/scala/spinaldb/Schema.scala`, `DbWriter.scala` | DDL and the batched JDBC writer (`org.xerial:sqlite-jdbc`). |
| `spinaldb/src/main/scala/spinaldb/Main.scala` | Generic entry point and the shared option parser. |
| `boom/` | BOOM entry (`spinaldb.boom.BoomDB`, settings in `boom/entry.sh`), a separate sbt build so generic use never loads a spinal-boom checkout. |
| `build-db.sh` | Wrapper used by people and by the MCP tool `query_build_db`. |

Tests: `cd spinaldb && sbt test` (elaborates GCD, GcdCluster and a loop design, checks the tables
with SQL; the BlackBox dependency test needs `yosys` on `PATH`, `source ../spinal-boom/env.sh`). The Python side is tested on SQL dumps of the same designs (`rvw/tests/data/regen.sh`).

## Decisions

- Keep the current schema and key contract in this README and C6. Rebuild databases
  with older schemas before diff. Navigation keeps its documented legacy readers.
- Write typed keys for comparison and short expression text for display.
- Propagate incomplete markers through every key and hash. Missing capture evidence
  cannot establish equality.
- Keep exact semantic-class checks and field allow-lists. Container override and
  compiler-field imitation defences are outside the C8 threat model.
- Compare generated internals by content. Preserve port identity, ordered tags,
  register sharing and synchronous memory-read state.
- Capture inputs before consumers use them. Preserve logical source aliases for navigation.
- Use one extraction for netlist tables, PDG, block diagrams and HGLDD. PDG SQL
  tables remain optional because they duplicate a large artifact.
- Keep BOOM settings in its entry. Keep the extractor reusable for other designs.
- Keep capture, ID assignment, register preparation, statement walking and table
  writing in that order. Deferred component tags can reference generated registers.
- Inout edges describe possible influence in both directions. They add no state.

## Limitations

- One elaboration of one configuration. Generate-time choices (Scala `if`s) are resolved; the
  database cannot say what another parameter value would build; diff two databases for that.
- Dependencies are structural: an edge means "can influence", not "does in this cycle". For values
  at a given time use SpinalTrace on a waveform (the PDG artifact feeds it).
- Assignment order matters in Spinal (last assignment wins); `drivers` lists them in elaboration
  order but does not compute the priority logic.
- Mixed-width memory ports and BlackBox internals are coarse (a BlackBox output depends on all its
  inputs). A BlackBox body is compared only when the two supported preprocessor contexts and the
  raw-source audit determine its dependencies. Other conditional defines or unresolved include
  names make it incomplete. The scan does not validate another tool's language semantics.
  Multiple clock domains are recorded per state node, but `path`
  does not reason about clock-domain crossings.
- SpinalHDL 1.15.0 can fail in `PhaseAnalog` before extraction when slices of a
  wider BlackBox inout attach to smaller top-level pads. SpinalDB does not change
  this backend limit. Bool pads and fixed-bit attachments have regression coverage.
- An attribute that names a file relative to a downstream tool's directory, under a name without
  `file` or `path`, is compared by its value only.
- Verilog line lookup (`where`) scans the generated Verilog if it still exists at `rtl_dir`.
- The stored HGLDD describes this elaboration's RTL. With the default naming phase that RTL has
  extra named probe wires (`mux_sel_*`, `index_*`, `mem_addr_*`) that a waveform from a plain
  simulation build does not contain; for Surfer on a plain build's VCD, build the database with
  `--no-pdg`, or simulate the RTL in `rtl_dir`.

`CrossDesignSpec` checks coarse BlackBox dependencies and analog/inout edges
with Verilog and SystemVerilog. It also checks database HGLDD against a VCD
from a separate plain Verilator build with PDG naming disabled. These are
bounded library fixtures. They do not qualify a complete core or dynamic causes.

### Other core builds

The [VexRiscv example](../examples/vexriscv/) enables PDG, block and HGLDD
artifacts. Its PDG can contain `no provider` warnings for plugin-generated
signals, including fetch response fields and stage stall conditions. Read the
`warnings` table before using it. Database navigation remains partial evidence.
It uses structural edges, not the PDG's cycle-specific execution model.
BlackBox inout attachments have conservative database edges, but the block
diagram currently omits their analog attachment nets. It shows the inout ports.

For a plain VexRiscv waveform, use `rvw/build-db.sh rv32im plain/design.db --no-pdg`.
Keep its RTL output separate from a database with PDG naming. HGLDD name
compatibility does not establish instruction correctness or dynamic trace coverage.

NaxRiscv's upstream build uses Scala 2.12.18 and a local development SpinalHDL
submodule. The workstation uses Scala 2.13.14 and SpinalHDL 1.15.0. Compiling
NaxRiscv sources unchanged with those workstation versions fails. Examples
include mutable `ArrayBuffer` versus immutable `Seq`, removed collection
operations and changed Spinal APIs. This is a build compatibility gap before
extraction. No NaxRiscv database or artifact support is claimed. A matching
Scala/SpinalHDL library build needs a separate integration check.

## Limit ownership

More-design validation: [#70](https://github.com/riscPrint/risc-v-workstation/issues/70). Non-Spinal queries: [#55](https://github.com/riscPrint/risc-v-workstation/issues/55). Consumer integration: [#69](https://github.com/riscPrint/risc-v-workstation/issues/69).

Retained limit: Best-effort source and parameter capture, incomplete keys, dependency refusals and local source paths remain deliberate restrictions. An incomplete identity cannot support reuse. No general extraction-completeness claim is made.

### Debug consumers

`SpinalDB/debug.sh --db design.db --out metadata --consumer export` writes the
PDG and all HGLDD files from one captured database. It records the database
identity in `metadata/database.json`. It does not elaborate the design.
Use `--consumer trace|gui|surfer|check` to launch a native consumer with these
files. Pass consumer arguments after `--`. See the SpinalTrace and SpinalWaves
READMEs for commands and waveform compatibility limits. SpinalBlocks is the third
database consumer; its integration is tracked in #44.

`Test/runMain spinaldb.LintFixtures DIR` also emits paired handshake/FIFO
clock-crossing topologies with a broken reverse path, and separate/merging
synchronizer paths. FIFO topology uses registered Gray encoders and a 4-word
memory. These are small structural references, not complete transfer protocols.
Run `RVW_LINT_FIXTURES=DIR python -m pytest rvw/tests/test_lint_extracted.py -q`
from the workstation root to check their extracted graphs.


## Verilog and SystemVerilog navigation

`rvw query build-hdl` uses native Yosys. It accepts the synthesizable subset of
`read_verilog -sv`. It writes the same C6 tables as SpinalDB. It does not need
SpinalHDL or sbt. Install Yosys separately and select it with `--yosys PATH`.

```sh
rvw query build-hdl --top top --out design.db top.sv leaf.sv
rvw query drivers u0.result --db design.db --json
rvw query loads request --db design.db --json
rvw query path request result --db design.db --json
```

The importer preserves module instances and named nets. Yosys lowers processes
before import. Generated bit signals connect the lowered cells. Paths are
conservative: each cell input can affect each output, and a named vector can
join disjoint slices. `sel` edges identify mux selects and enable ports.
Clock and reset pins do not become value dependencies. State outputs stop
combinational traversal. When one visible name holds a bit, hidden Yosys
temporaries are its aliases; only visible names become registers. A constant
on a child input, or a child output tied to a constant, becomes a
`Yosys constant` assignment. A cell that reads its own output keeps the
self-edge (a real loop), as SpinalDB does.

Each flip-flop cell gives a `clock_domains` row: the clock and reset nets are
followed through ports to a toplevel input, `clock_edge` comes from
`CLK_POLARITY`, `$adff`/`$adffe`/`$adlatch` give `ASYNC` resets and
`$sdff*` give `SYNC` resets with their polarity, and `reset_value` holds the
cell's reset value parameter. Registers record `clock_domain_id`; clock and
reset roots get `clock_role`. Synchronous resets written as plain mux logic
stay data, because `proc` does not make `$sdff` cells. `rvw lint` CDC/RDC uses
these rows for non-Spinal designs.
Assignment text describes the lowered cell or net alias. Process source ranges
can cover several statements. These results are navigation evidence.

Memories get a `mem` signal and a `memories` row (width, depth, initial words).
Write ports drive the memory node (`data` from the data, `sel` from address and
enable). Read ports depend on the memory and on their address. A clocked read
port output is a register. Port expressions and memory keys stay unknown.
A cell with several outputs and several inputs gets one hidden `$cell$N` hub, so
the edge count stays linear in its ports. `$buf` cells connect bit to bit.
A bit node that no single visible net holds is named after one owner,
`q_o[3]` (query name `q_o.3`).

The native frontend refuses blackboxes, unresolved modules, inouts, unknown
cells, include directives, source remapping and file-reading tasks. Supply all
self-contained translation units explicitly. It captures source bytes and the
Yosys executable identity before compilation. It publishes the database with
atomic replacement. A failed build leaves an existing output intact.
Semantic diff keys stay incomplete. Self-diff cannot report hardware identity.
Every HDL database carries a SpinalBlocks diagram, artifact `blocks.json`
(see `SpinalBlocks/README.md`). No PDG is generated.

The native integration tests accept read-only SERV and Ibex reference clones.
Set `RVW_HDL_REF` to their parent directory. The tests use SERV `serv_top` with
its external register-file interface and Ibex `ibex_counter`, not a full Ibex core.
The reference clones are not modified. Missing clones cause explicit skips.

```sh
git clone https://github.com/olofk/serv.git ref/serv
git -C ref/serv checkout f200eb2ed7b69ac1c6b8eddd47654522aeee5ce8
git clone https://github.com/lowRISC/ibex.git ref/ibex
git -C ref/ibex checkout 2c72091c12187b5c7caf925aa911c94b806aab54
git clone https://github.com/stnolting/neorv32.git ref/neorv32
git -C ref/neorv32 checkout 7bd0858
RVW_HDL_REF="$PWD/ref" rvw/.venv/bin/python -m pytest rvw/tests/test_query_hdl.py rvw/tests/test_query_slang.py rvw/tests/test_query_ghdl.py rvw/tests/test_query_chisel.py -q
```

### Full SystemVerilog with slang

`--frontend slang` elaborates through the yosys-slang plugin (`read_slang
--keep-hierarchy`). It accepts packages, interfaces, generate blocks, enums,
structs and include files. Pass `-I DIR`, `-D NAME[=VALUE]`, `-G NAME=VALUE`
(top parameters) and `--std`. The plugin is `--slang PATH`, then `$RVW_SLANG`
(`scripts/install.sh --with-formal` builds a pinned one), then the plugin that
OSS CAD Suite ships beside Yosys.

```sh
P=ref/ibex/vendor/lowrisc_ip
rvw query build-hdl --frontend slang --top ibex_core --out ibex.db \
  -I $P/ip/prim/rtl -I $P/dv/sv/dv_utils $P/ip/prim/rtl/prim_util_pkg.sv \
  ref/ibex/rtl/ibex_pkg.sv ref/ibex/rtl/ibex_*.sv   # the core files of ibex_core.f
rvw query component cs_registers_i.u_mepc_csr --db ibex.db   # parameters: Width=32'd32, ...
```

Before elaboration, the whole directory of each source and each include
directory is captured. slang reads only these copies, so local and `-I`
includes resolve inside the capture. `input_files` lists every captured file.
File-reading tasks and source remapping are refused. Assertions and initial
blocks are ignored (`--ignore-assertions --ignore-initial`).

A second slang pass dumps the JSON AST (`--dump-ast --ast-compilation-only`).
It gives the value of each non-local parameter per instance (artifact
`hdl/parameters.json`, shown by `rvw query component`) and the declared SV type
of each variable, net and port (`signals.type`, e.g. `p::state_e`,
`logic[31:0]`). Component paths keep generate names (`g[1].u`); query them as
`g[1].u` or `g.1.u`. `meta.hdl_options` records include directories, defines,
parameters and the standard. `meta.slang_plugin_sha256` records the plugin.
`$aldff` cells with a constant load value are async resets.

Ibex `ibex_core` at the pinned revision below (all core files, `ibex_csr`
instances, ROM memories) builds in about 7 s: 32 components, 49k signals, 179k
edges. Use the same graph limits as the native frontend. The register file
and the instruction cache are outside `ibex_core`; `ibex_top` also needs the
`prim` generic cells.

### VHDL with GHDL

`--frontend ghdl` analyzes and elaborates VHDL through the GHDL Yosys plugin
(`ghdl --std=08 --work=LIB files -e TOP`). Pass `--library NAME` for the work
library, `-G NAME=VALUE` for top generics and `--std 93|08` (default `08`).
The plugin is `--ghdl-plugin PATH`, then `$RVW_GHDL_PLUGIN`, then the plugin
that OSS CAD Suite ships beside Yosys. `GHDL_PREFIX` defaults to OSS CAD
Suite's `lib/ghdl`. Some OSS CAD Suite builds ship a plugin made for another
Yosys memory-cell API; VHDL memories then fail the Yosys cell check. Build a
matching plugin outside the checkout with `scripts/build-ghdl-plugin.py`
(pinned plugin revision, GHDL headers of the exact libghdl commit). It prints
the `RVW_GHDL_PLUGIN` export.

```sh
python3 scripts/build-ghdl-plugin.py          # ~/.cache/rvw/lib/ghdl.so
export RVW_GHDL_PLUGIN=~/.cache/rvw/lib/ghdl.so
N=ref/neorv32
rvw query build-hdl --frontend ghdl --library neorv32 --top neorv32_cpu --out cpu.db \
  $(sed "s#\$NEORV32_HOME#$N#" $N/rtl/file_list_core.f)
rvw query where cpu_regfile_inst.rf_we --db cpu.db   # neorv32_cpu_regfile.vhd:53
```

The plugin writes no source attributes. A second pass, `ghdl --file-to-xml`,
reads the VHDL AST of the same captured files. It gives the line of each
entity (component location), each port and signal declaration (signal
location) and the first assignment statement to each signal (its assignment
location). Bit nodes and lowered cells without a named target have no line.
GHDL names a specialized architecture `<entity>_B<arch>...`; the component
`module` is the entity. Record fields are separate nets (`dbus_req_o[addr]`).
Generate instances keep GHDL's names: `g:1.u` is the first iteration of `g`,
whatever its index value. GHDL inverts active-low resets for its flip-flops;
clock-domain roots follow ports, aliases, buffers and inverters, so the
domain reports the input's own polarity (`rstn_i`, active low). A control net
that other logic derives is its own root.

NEORV32 `neorv32_cpu` at `7bd0858` (9 components, 3 memories, 44k edges) builds
in about 5 s of CPU. `meta.hdl_options` records the standard, library and
generics; `meta.ghdl_version` and `meta.ghdl_plugin_sha256` the tools.
Mixed-language designs and foreign VHDL attributes are not supported.

### Chisel through FIRRTL and firtool

`--frontend chisel` takes one FIRRTL file (`ChiselStage.emitCHIRRTL`). firtool
(`--firtool PATH`, then `$RVW_FIRTOOL`, then `PATH`; Chisel caches its own copy
under `org.chipsalliance.llvm-firtool`) lowers it to split Verilog and HGLDD
with `-g --emit-hgldd --disable-all-randomization` and plain location comments.
The native reader imports the Verilog with `-DSYNTHESIS`, then `opt_dff` folds
Chisel's synchronous resets into `$sdff` cells, so registers get `SYNC` reset
domains and reset values.

```sh
rvw query build-hdl --frontend chisel --top Top --out top.db Top.fir --source-root .
rvw query where io.a.valid --db top.db            # Chisel name; Gen.scala:21
rvw query drivers units_0.acc --db top.db         # Gen.scala:13, SYNC reset to 00000000
rvw query export hgldd/Top.dd Top.dd --db top.db  # for SpinalWaves/Surfer
```

firtool writes `// Gen.scala:13:20, :15:16` after each Verilog line. Each
database location on an emitted line is rebound to Scala: declarations take
the first location of the line, assignments the last. A Scala path binds only
when the file exists under a `--source-root` (default: the FIRRTL file's
directory); it is then captured in `input_files`. Locations left on emitted
Verilog are cleared, since that Verilog is not a captured source. The emitted
files are artifacts `rtl/*.sv`; `hdl/source-map.json` maps each of their lines
to its Scala locations; `hgldd/*.dd` is firtool's HGLDD. HGLDD names become the
second spelling of each signal (`spinal_path`, `io.a.valid` for `io_a_valid`);
firtool temporaries (`_*`) keep their Verilog name. firtool fuses locations,
so a connect can show the register or operator line instead of its own.
`meta.firtool_version` and `meta.firtool_options` record the compiler.

See [the design](../docs/design/hdl-frontends.md) for the remaining phases.
