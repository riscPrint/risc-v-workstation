# rvw query

Text `where` shows the origin and clock domain of a synchronous memory read state node.
These database nodes have no Verilog or waveform name.

Questions about an elaborated Spinal design, answered from a SpinalDB design database
(`SpinalDB/README.md`). Every command prints text, or JSON with `--json`; the MCP tools
`query_*` (see `../mcp/README.md`) return the same JSON.

```sh
cd rvw && uv venv && uv pip install -e '.[dev,mcp]'
export RVW_DESIGNDB=../SpinalDB/out/boom-small.db     # or --db PATH on each command
```

| Command | Answers |
|---|---|
| `info` | toplevel, configuration, source revision, counts, clock domains, artifacts, RTL files, warnings |
| `where SIGNAL` | Scala declaration line, Verilog module/name/line, waveform path, Spinal path, Area, type, clock and reset; for a bundle/Area, its type and signals |
| `drivers SIGNAL` | every assignment: source expression, `when`/`switch` condition chain, enable, Scala line, the component the statement is in; for registers clock, reset signal/kind/polarity and reset value; for memories the ports; for undriven signals why (primary input, clock, BlackBox) |
| `loads SIGNAL` | signals reading it and how (`data`, `cond`, `sel`), the statements and the conditions that use it |
| `fanin SIGNAL --depth N` / `fanout` | transitive drivers/readers, `--stop-at-regs`, `--kind data` etc.; registers and ports reached |
| `path A B` | shortest dependency paths from A to B: each hop with the statement that links it and its Scala line, and the number of register stages; `path A A` finds the shortest feedback loop through A (at least one hop); `--comb-only`, `--data-only`, `--max-paths` |
| `search PATTERN` | signals and components by substring, glob (`lsu*stq*commit*`) or `--regex`; `--kind reg|wire|port|mem|component`, `--scope COMPONENT` |
| `hierarchy [PATH] --depth N` | component tree: instance, Verilog module, Scala class, location |
| `component PATH` | ports, interfaces (Stream, Flow, Vec, bundles with direction and width), children, registers, memories, Areas, counts |
| `regs PATH [-r]` | registers with width, clock, reset value, location |
| `diff OLD.db NEW.db` | typed hardware changes in components, ports, registers, memories, signals, assignments and connections; includes emission settings, ordered tags and port order; needs schema `/20` on both sides; `--scope`, `--no-connections` |
| `explain OLD.db NEW.db [--coverage COV.json] [--effect CMP.json]` | each difference of `diff` with its Scala locations, the tests that hit base coverage points on those lines, and a measured effect of the whole change; uncertain items (added hardware, no location, unmapped or unhit lines) select every test |
| `export blocks|pdg|hgldd OUT` | write an artifact of the same elaboration (SpinalBlocks diagram, SpinalTrace PDG, SpinalWaves HGLDD) |

## Names

`SIGNAL` may be written the way it was found:

- Verilog: `tile.core.rob_1.rob_head`, `BoomSimTop.tile.core.rob_1.rob_head`, `Rob.rob_head` (a
  module instantiated once), `rob_head` (a unique name);
- waveform: `TOP.BoomSimTop.tile.core.rob_1.rob_head`, `TOP/BoomSimTop/.../rob_head[4:0]`;
- Spinal: `tile.core.rob_1.io.enq.valids(0)`, `lsu.stq_committed(3)`, `fifo.logic.ptr.push`
  (Areas), mixes such as `rob.io.enq_valids_0`;
- instance names without Spinal's dedup suffix: `rob.rob_head` finds `tile.core.rob_1.rob_head`.

An ambiguous name is an error that lists the candidates; no candidate is picked silently, also
when several signals share one Spinal path (6 such paths in BOOM small, e.g.
`tile.frontend.ftq.redirect_new_entry_regNext.br_mask` names `..._br_mask` and `..._br_mask_1`)
or when only one of several same-named signals is not a compiler temporary (`_zz_4`). Use an RTL
path then. For `where`, `fanin`, `fanout` and `path`, a bundle or
Area path stands for all its signals (`tile.dcache.io.lsu.resp`), so `path` works between
interfaces. Compiler temporaries (`_zz_*`, `when_*`) are transparent in the graph: answers are in
named signals, with the strongest dependency kind along the hidden part.

## Stale databases

Rebuild inout databases made before the round 24 fix. BlackBox inouts can read and drive.
Analog net attachments connect in both directions. These links add no register stage, so
`--comb-only` can traverse them. The edges show possible dependencies, not whether a pad is
driving for a given input value. Graph queries and connection diffs refuse a database that lacks
required BlackBox inout edges or reverse edges between attached inout ports. The schema stays
`rvw.designdb/20`; the table layout and typed-key format did not change.

A database records the checkout it was built from (`core_repo`, `core_rev`, `core_dirty` from
the BOOM entry, or `source_repo`, `source_rev`, `source_dirty` given with `--meta`). Every
query compares them with the checkout now and warns on stderr, and in `db_warnings` of the JSON
and MCP results, when the checkout moved to another commit, has uncommitted changes, or the
database was built from uncommitted changes. The answer is still given; rebuild the database to
trust it. Without those meta rows nothing is checked.

## Examples on BOOM small

```text
$ rvw query drivers rob.rob_head
tile.core.rob_1.rob_head reg UInt[5]
  register on clk (RISING), reset reset (SYNC, active high) to 0
  := next_rob_head
      at .../boom/exu/rob.scala:212 (in tile.core.rob_1)
$ rvw query drivers rob.next_rob_head
  := rob_head                                      at .../rob.scala:211
  := (rob_head + 1)(4 downto 0)
      under when(finished_committing_row)          at .../rob.scala:679

$ rvw query path tile.dcache.io.lsu.resp tile.core.iregfile.io.write_ports --data-only --max-paths 1
path 1: 7 hops, 2 register stages
  tile.dcache.io_lsu_resp_0_payload_data wire out UInt[64]
  -data-> tile.lsu_1.io_dmem_resp_0_payload_data wire in UInt[64]         (tile.scala:75)
  -data-> tile.lsu_1.iresp_0_payload_data wire UInt[64]                    (lsu.scala:1540)
  -data-> tile.lsu_1._zz_io_core_iresp_0_payload_data reg UInt[64]         (lsu.scala:1479)
  -data-> tile.lsu_1.io_core_iresp_0_payload_data wire out UInt[64]
  -data-> tile.core.io_lsu_iresp_0_payload_data wire in UInt[64]           (tile.scala:60)
  -data-> tile.core.io_lsu_iresp_0_payload_data_regNext reg UInt[64]       (core.scala:876)
  -data-> tile.core.iregfile.io_write_ports_0_payload_data wire in UInt[64]

$ rvw query diff boom-small.db boom-medium.db --no-connections
  + component tile.core.alu_exe_unit_1
  ~ register tile.core.alu_exe_unit_0.arb_uop_payload_br_mask: width 8 -> 12
  ...
```

## Code

`db.py` (opening, name resolution, row helpers), `ops.py` (the queries and the dependency graph
with transparent temporaries), `diff.py`, `cli.py` (argparse and text output), `mcp_tools.py`
(MCP tool specs). Tests: `rvw/tests/test_query.py` on SQL-dump fixtures (`rvw/tests/data`).

## Decisions

- Open one captured database per query. Close it when the call ends. Diff shares
  one capture across its two files and closes both databases on every exit path.
- CLI and MCP use the same operations and return the same JSON. Invalid names,
  ambiguous paths and invalid regular expressions return query errors.
- Navigation reads schemas `/1` through `/20`. Diff needs `/20` on both sides.
  Rebuild older databases before comparing them. Synchronous memory dependency
  queries need the state representation introduced in `/17`.
- Compare stable external paths and typed keys. Display text alone masks generated
  names. Structured lists and dictionaries preserve comparison boundaries.
- Generated internals are transparent for navigation. Registers, memories and
  synchronous read state remain boundaries. Diff hides unstable memory-read names.
- Preserve ports even when their names are generated. Preserve assignment order,
  register sharing, port order and tag order.
- Unknown keys produce undetermined paths. Missing or invalid capture evidence
  produces an inconclusive result. Neither can establish `identical: true`.
- Include clock signals when they carry data. `--include-clock` controls stored
  clock-domain relations in legacy databases. Current extraction writes no such edges.
- Warn when revision metadata differs from the checkout. A warning does not rebuild
  the database. Source and RTL locations use their captured content bindings.
- Keep BOOM examples and fixtures separate from generic query code. See
  `SpinalDB/README.md` for the key model, column reference and extraction limits.

## Limit ownership

More-design validation: [#70](https://github.com/riscPrint/risc-v-workstation/issues/70). Non-Spinal inputs: [#55](https://github.com/riscPrint/risc-v-workstation/issues/55).

Retained limit: SpinalDB extraction and incomplete-key restrictions apply to every query and diff.

## Native debug consumers

From the workstation root, run `SpinalDB/debug.sh --db design.db --out metadata`.
This exports PDG and all HGLDD files from one captured database. It also writes
`database.json` with the database identity and artifact hashes. The output
directory must be empty. `--consumer trace|gui|surfer|check` launches a native
consumer. Pass its arguments after `--`. Use `--timeout SECONDS` for bounded checks.
See the SpinalTrace and SpinalWaves READMEs for commands and waveform limits.
The launcher does not elaborate or build the design.


`rvw query build-hdl --top MODULE --out DB FILE...` builds a C6 navigation
database from Verilog and the native Yosys SV subset. `--frontend slang` takes
full SystemVerilog through yosys-slang (`-I`, `-D`, `-G`, `--std`) and adds
per-instance parameters (shown by `component`) and declared SV types.
`--frontend ghdl` takes VHDL through the GHDL Yosys plugin (`--library`, `-G`
generics, `--std`) with VHDL declaration and assignment lines.
`--frontend chisel` takes one FIRRTL file through firtool, maps locations to
Scala lines (`--source-root`) and accepts Chisel names. MCP: `query_build_hdl`. `--yosys PATH` selects the
native tool. `--timeout SECONDS` bounds elaboration. Drivers, loads and paths use
the same reader. HDL graphs are conservative and semantic diff is inconclusive.
See [the frontend limits](../../../../../SpinalDB/README.md#verilog-and-systemverilog-navigation).

## Explained diffs (`explain`)

`rvw query explain OLD.db NEW.db` (MCP `query_explain`) returns `rvw.diff-explain/1`. Each item
is one `diff` entry (component, port, register, memory, signal, logic or connection) with:

- `locations`: the signal's declaration and its assignments' Scala lines (old database for
  changed and removed items, new database for added ones);
- `tests`: with `--coverage` (an `rvw.coverage/1` database of the OLD revision), the tests that hit
  a coverage point mapped to one of those lines. Status `covered`, `unhit` (mapped, never hit),
  `unmapped` (no point on those lines), `uncovered` (added hardware) or `unknown` (no location
  or no coverage). Files match by path, or by a common tail of at least three path parts;
- `effect`: always `unknown` per item.

`selection.mode` is `covering` only when every item is `covered`; otherwise `all`, and
`selection.tests` lists every coverage test. With `--effect` (an `rvw perf compare` or
`rvw arch compare` JSON), `effect.status` is `measured` for the whole change; it is never
attributed to one difference. No performance model runs here.

The slang native tests also cover SERV `serv_top` at revision
`f200eb2ed7b69ac1c6b8eddd47654522aeee5ce8`. They compare 16 cross-instance
path queries with an independent traversal of the native netlist. Set
`RVW_HDL_REF` to a directory with the external `serv` checkout to run this test.

## Agent semantic queries

`definition SIGNAL` returns the captured declaration. `references SIGNAL`
returns assignments, readers and condition uses across hierarchy.
`parameters [PATH]` returns per-instance values when the front end captured them.
`explain-module [PATH]` returns `rvw.module-explanation/1` with ports, children,
registers, memories and clock domains. It does not infer module intent.
`hierarchy-diff OLD NEW` compares instance paths, modules and captured parameters.
It can compare HDL databases without claiming semantic logic equivalence.
`type EXPRESSION` returns the captured signal type and width. Constant bit and
part selects use normalized zero-based positions. Other expressions return an
error because the database has no HDL expression type checker.
`port-status [PATH]` reads captured native instance connections: connected,
tied to known bits, unconnected, or unknown. Old databases return unavailable.
All commands accept `--json`. MCP names use the `query_` prefix and underscores.
Source locations describe the captured database. Rebuild after source edits.

## Source-hash build cache

Pass `build-hdl --cache-dir DIR` to reuse an unchanged design database.
MCP `query_build_hdl` accepts `cache_dir`. Keep the cache and output database
outside source directories. The key includes source content, source paths,
ordered options, tool binary and plugin hashes, Scala source roots for Chisel,
and translator/schema code. Slang also hashes files in source and include trees.
A hit copies the stored database without native elaboration. A changed key runs
a full elaboration. This does not rebuild individual modules in isolation.
The result includes `cache.key`, `cache.status` (`hit` or `rebuilt`) and
`cache.scope` (`whole-design`). Damaged cache entries are rebuilt.
Tool shared libraries and environment settings other than the selected plugins,
firtool and GHDL prefix are not hashed. Clear the cache after tool environment
changes. Builds without `--cache-dir` keep their prior behavior.

The GHDL native tests also cover `neorv32_uart` with four-entry RX and TX
FIFOs at NEORV32 revision `7bd0858bed243e5e32521a8ffbeef8c68b68c653`.
The test compares 16 path queries with an independent GHDL/Yosys netlist
traversal. It checks two memories and the original RX input declaration line.
Exact connectivity is inconclusive: packed-vector aliases add paths that the
native bit graph does not have. The test reports xfail for these extra paths.
A missing native path is a failure.
