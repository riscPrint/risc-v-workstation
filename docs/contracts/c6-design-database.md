# C6. Design database (`rvw query`)

One elaboration of a Spinal design, written by `SpinalDB` as a SQLite file with schema
`rvw.designdb/20` (`meta.schema`; `/2` added typed expression keys, memory init hashes and
write masks; `/3` keys compiler temporaries by their own assignments; `/4` adds clock-enable and
soft-reset polarity to clock domains and keys generated registers by content at their operand
position; `/5` does so at any depth (`$reg:<id>`, a canonical id of the register graph) and marks keys that
cannot be complete with `$incomplete:` (hashed parts `h!:`); `/6` adds the typed keys of each clock
domain's control signals and writes generated registers as `$reg:<hash>#<rank>`, so equal registers
stay distinct; `/7` applies the allow-list rule: anything the keys do not model, and a BlackBox
whose external body was not hashed, is `$incomplete:`, and memory ports, BlackBox generics,
`initial` values, assertions and tags are keyed; `/8` keys an enum by its element names in order
and each element's encoded value, and hashes every file a BlackBox body includes (a body whose
dependency set Yosys cannot list is `$incomplete:`); `/9` keys a `switch` default by every case key
(empty cases included) and a case by the earlier keys that can block it, writes the tags and
attributes of generated registers and temporaries into their keys, and adds `components.tags`;
`/10` flags a `when_`/`switch_` line name `generated` only when Spinal gave it (a user signal named
like one is a named signal), keys a Scala `object` tag by its fields, and adds `signals.port_index`,
each port's place in its module's emitted port list; `/11` writes every value in a key with one
canonical encoder (strings quoted and escaped, numbers and booleans typed, sets and maps in sorted
order, nested keys length-framed), labels enum-like Spinal values by name (never an identity
`toString`), keys an attribute subclass by its emitted languages, tag flags and fields, and keys
every field of a Scala `object` tag but the compiler's `MODULE$`, `serialVersionUID` and lazy-val
bitmaps; `/12` keeps tags and attributes in the order Spinal emits them (two `init` attributes in
either order differ), leaves out of a tag object only fields the Scala compiler provably added
(exact shape, and the name not declared in the Scala signature; a user's `var bitmap$0` is keyed;
unprovable: `$incomplete:`), and keys constant `final val`s, which have no field; `/13` reads a
case-class (any `Product`) tag payload by every field it holds, written `Class(name=value,...)`
sorted by field name, never through `productIterator` or another method the class can override,
and reads JDK big numbers, Scala library collections, `ClockDomain` and the Spinal tags written in
short forms only as their exact classes (a subclass is read by its fields or is `$incomplete:`);
`/14` adds `meta.emission_config` and applies the exact-class numeric allow-list to literal
values, poison masks, enum encodings, switch masks and memory init words. Rejected numeric
payloads stay `$incomplete:`, including outside memory init hashes. The emission key records every
config field except audited file placement, file splitting, comments, logs and source-location
collection. In `/14`, user phases, callbacks and nonempty scope properties were incomplete.
`/20` extends this rule with compiled-code keys, described below. Unknown values remain incomplete.
A report made outside `SpinalDB.elaborate` has an incomplete emission key. Diff compares this key
at the top level even with `--scope` or `--no-connections`. A changed setting is a difference;
a missing or equal incomplete key gives `identical: null` at `<emission_config>`.
Assignment targets use their union: a missing side has an empty driver list.
`/15` requires exact class identity, classloader and code source for library membership. A package name
alone cannot make an expression complete or remove a tag payload. Ignored bookkeeping tags use
exact classes. Older databases can hold forged complete keys despite the same table layout.
`/16` applies the identity check to signal declarations, expression references and generated keys:
they retain the signal-type allow-list. Unsupported signal classes remain incomplete, including unread
generated declarations. Container override and anonymous-Area forwarder checks are outside the C8
threat model. Compiler bookkeeping fields are omitted by exact name, modifiers and type. Constant
`final val` values are read from Scala signatures; missing constant metadata remains incomplete.
Yosys runs through the resolved launcher recorded by `Capture.tool`. Its path, hash and observed
version do not establish transitive tool dependency identity; `verify_tools` still checks recorded tools.
Unread unsupported generated declarations also mark their component incomplete. Conservative
BlackBox edges include clock-role input ports. An unknown diff scope is an error; a scope present
on one side still reports additions or removals.
`/17` hashes BlackBox dependencies from two independent Yosys contexts: implicit `SYNTHESIS`
and `-nosynthesis`. The fingerprint covers their union. Raw-source checks make unsupported
conditional defines, macro-built includes and context-changing directives `$incomplete:`. The scan
does not infer external defines or include directories. Both contexts must resolve under the
supplied generics. Timeouts and cancellation use `rvw.common.proc.run_group` through
`SpinalDB/scripts/hdl-deps.py`.
`/18` reads each inline Verilog body once before emission. The emitter and fingerprint use
that same value. One shared C8 capture supplies all external HDL roots, supplied sources, literal
includes and file-valued attributes before Yosys reads them. Both contexts use private copies.
`input_files(path, resolved, sha256, size, record)` and `meta.input_capture` bind file and tool
identities. Unsupported capture gives an incomplete key. A failed capture invalidates its batch.
`diff` requires a valid capture record with no capture problems; otherwise it is inconclusive.
Database publication closes a private sibling file, then uses one atomic rename. Query readers
capture that single file before opening SQLite; WAL inputs are refused. `where` checks private
RTL copies against `input_files` before reporting a line. Missing or changed RTL gives
`status: inconclusive` without a live Verilog line. Scala location files are captured and checked
against the same table. A missing or changed Scala file leaves only `stored_loc` and an
inconclusive status. These hashes do not prove compiler input bytes. Query results include the
database `input_capture`; `where` also includes `location_capture`. Artifact export uses an
atomic file replacement.
Default navigation roots are optional. The capture record lists each under
`optional_source_roots` with `state: present|absent`. Explicit roots are required.
Navigation bindings retain logical tree member paths and captured symlink provenance.
`where` matches stored lookup or resolved paths, including aliases proved by a captured tree
layout. An unrecorded alias has no binding, even when it resolves to the same live file.
`/19` keys every input, output and inout reference by its stable external path before
temporary expansion. Generated-name ports retain their identity in every operand position.
Each synchronous memory read output has a database-only `mem_read` state signal linked by
`mem_ports.output_id`. Memory, address and enable dependencies enter the state. Combined ports
also include write enable, data and mask dependencies. Consumers read that state. It has the
port's clock domain and no RTL or waveform name. `path` counts it as one register stage;
`--comb-only` and `--stop-at-regs` stop there. Asynchronous reads stay combinational.
Dependency graph queries refuse older databases with synchronous reads, because they lack these
boundaries.
`rvw query diff` requires `/20` and refuses `/19` and older files with an error to rebuild the
database with the current SpinalDB. Navigation queries still read older schemas. Diff
reports `identical: null` with the affected paths under `undetermined` when a current key is
incomplete). The tables are documented column by column in
`SpinalDB/README.md`; this section is what other tools may rely on.

- **Build**: `SpinalDB/build-db.sh ENTRY CONFIG OUT.db` (a named entry `SpinalDB/ENTRY/` whose
  `entry.sh` sets its environment and lock; `boom` builds BOOM and holds the `boom` lock) or
  `SpinalDB/build-db.sh class TOP_CLASS OUT.db` (any component with a no-argument constructor);
  from Scala, `spinaldb.SpinalDB.generate(config, file)(new Top)`.
- **Find it**: tools take `--db PATH`; the default is `$RVW_DESIGNDB`, then `./design.db`.
- **Names**. Every signal has `path`: the instance path below the toplevel plus the Verilog name
  (`tile.core.rob_1.rob_head`), which is also the waveform path below the scopes in
  `meta.extra_scopes` (`TOP BoomSimTop`), and the SpinalTrace PDG symbol. `spinal_path` is the
  typed Spinal path through bundles, Vec indexes and Areas (`tile.core.rob_1.io.enq.valids.0`).
  Components have `path` (the same instance path, `""` for the toplevel) and `module` (the Verilog
  module name). `rvw query` resolves Verilog, waveform and Spinal spellings to these (see
  `rvw/src/rvw/query/db.py`); other tools should store `path` when they refer to a signal.
- **Facts**: components, Areas, bundles (Stream/Flow/Vec/...), signals (kind `reg|wire|mem|mem_read`,
  direction, type, width, clock domain, reset value, generated, pruned), memories and ports,
  assignments (source text, `when`/`switch` condition chain, enable, Scala `file:line`), and the
  signal dependency graph `edges(src, dst, kind)` with kinds `data`, `cond` (when/switch
  conditions), `sel` (mux selects, dynamic indexes, memory addresses), `init` (reset values),
  `blackbox`. These edges remain visible when either signal has a `clock_role`. Clock-domain
  relations are stored in `clock_domains`, not as clock edges in `/15`. The graph does not infer
  a data dependency from a domain relation. `--include-clock` has no additional relations to
  include in this schema; it never changes whether ordinary data edges are kept.
- **Artifacts** of the same elaboration (table `artifacts`, gzipped): `pdg.json` (SpinalTrace),
  `blocks.json` (SpinalBlocks), `hgldd/<top>.dd` (SpinalWaves). `rvw query export blocks|pdg|hgldd
  OUT` writes them out, so a viewer needs no elaboration of its own.
- **Queries**: `rvw query info|where|drivers|loads|fanin|fanout|path|search|hierarchy|component|regs|export|diff`,
  all with `--json`; the MCP tools `query_*` return the same JSON.

`/20` keys user phases and other user emission objects by exact class name, SHA-256 of the
captured class bytes, SHA-256 of the whole classpath entry, and the ordered captured classpath.
A directory entry covers all files, including helper classes and resources. A jar entry covers
its exact bytes. All hashes use private in-memory copies made before the user phases run.
The key omits source paths. It reads instance state, including inherited fields, by reflection.
Known collections preserve their element keys and order. Supported immutable values are strict
Scala library `List` (`::` and `Nil`), `Vector`, `Queue`, `ArraySeq`, `Range`, factory sets and maps,
`HashSet`, `ListSet`, `BitSet`, `HashMap`, `ListMap`, `VectorMap`, `TreeSet`, `TreeMap`, `Some`,
`None` and tuples of supported values. Their runtime classes need the library class, loader and
jar identity check. Keys retain the runtime class and iteration order. Sorted sets and maps also
key their ordering state. Range keys retain bounds and step. User collection subclasses, lazy
sequences, views, maps with defaults and unsupported values remain incomplete.
Unknown library values, cycles,
missing class bytes, missing code sources, nested classpath symlinks, unsupported lambda metadata and capture limits stay
`$incomplete:`. A size, mtime or file-set change invalidates the key. The capture limit is 512 MiB
and 100,000 entries per classpath directory. Whole-entry and whole-classpath changes can produce
conservative differences even if the changed code does not affect this design.
JVM hidden lambdas have no stable runtime class name or readable class resource. Their key uses
the exact compiled owner and implementation class, method name, descriptor, method kind,
functional interface and captured arguments. Only the JVM-generated metadata accessor on a
checked hidden synthetic nestmate is invoked. Ordinary user serialization hooks, formatters and
payload methods never decide a key. User phase lists are captured before the tools add phases.
Reports made outside `SpinalDB.elaborate` remain incomplete. Diff refuses `/19` and older schemas.
This records compiled code and instance state. Arbitrary generator reads of files, environment
variables or mutable global state are not a captured input contract.


### C6 native HDL navigation subset

`rvw query build-hdl --top MODULE --out DB FILE...` writes `rvw.designdb/20`
with `meta.frontend=yosys-verilog`. Root component path is empty. `spinal_path`
equals the HDL signal path. `meta.graph_semantics` declares conservative signal
and whole-cell dependencies. Query JSON repeats `frontend` and `graph_semantics`.
Named vectors can join disjoint bit slices. These are navigation paths, not
bit-exact functional cones. `data` edges represent value reads. `sel` edges
represent selects and enable/reset inputs. Flip-flop and latch outputs have
kind `reg`; clock inputs are excluded from value edges. Register stage counts
can include multiple aliases of the same state. Clock domains and reset
values are unknown. Empty artifact tables do not imply completeness.

Sources and executable identity use C8 capture. Include directives, file input,
source remapping and token concatenation are refused. Source locations bind to
captured HDL files in `input_files`. Input errors do not publish a partial DB.
Semantic keys and emission configuration are `$incomplete:`. Diff must remain
inconclusive. This subset adds no C1 runtime or formal model claim.

### C6 HDL front ends: slang and memories

`build-hdl --frontend slang` writes the same tables with `meta.frontend=yosys-slang`,
`meta.hdl_options` (JSON: `include_dirs`, `defines`, `parameters`, `std`) and
`meta.slang_plugin_sha256`. C8 capture covers the whole directory of each source
and each include directory before elaboration; `input_files` lists those files.
Artifact `hdl/parameters.json` maps each component path (root `""`) to its
non-local parameter values as slang prints them. `signals.type` holds the declared
SV type when the AST names one, else `Bits`. Component paths can hold generate
indexes (`g[1].u`); `spinal_path` is the dotted form (`g.1.u.q`), which the
reader's name normalization matches. Every HDL front end now imports memories:
kind `mem` signals, `memories` rows with `key=$incomplete:hdl-memory`, `mem_ports`
rows with `key=$incomplete:hdl-memory-port`, and `mem_write` assignments.
Hidden `$cell$N` hub signals carry whole-cell dependencies. All `yosys-*`
frontends share the graph semantics of the native subset above.

### C6 debug metadata export

`SpinalDB/debug.sh` reads one C8 capture of a design database. It writes stored
`pdg.json` and `hgldd/*.dd` bytes without a new elaboration. `database.json` holds
`input_capture` (the C8 database record), `meta` (database metadata), and `artifacts`
(entries with `name`, uncompressed `bytes`, and uncompressed `sha256`). Surfer and
checker mode export HGLDD only. Trace, GUI and export mode require PDG and HGLDD.
The output directory must be empty. Native consumer exit codes pass through.
This export establishes artifact identity, not waveform or dynamic trace parity.

### VIP JTAG topology

`rvw.vip.jtag-topology/1` exports ordered TAP declarations with instruction
lengths, TDI/TDO pins, test resets, access requirements and selected modes.
It reports missing adjacent connections and unreachable modes against the
caller-supplied graphs. Missing either graph gives `inconclusive` unless a
mismatch is already observed. `checked` covers only the supplied graphs.
The format carries no RISC-V debug conformance or extracted-design claim.
