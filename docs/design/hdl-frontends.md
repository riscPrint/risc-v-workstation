# HDL design database front ends

## Goal

Populate C6 for Verilog and SystemVerilog without changing query names or graph
semantics. Keep #26 as the non-Spinal umbrella. Keep #55 as its query child.
The first increment uses native Yosys. It accepts the synthesizable subset of
`read_verilog -sv`. It does not claim complete SystemVerilog support.

## Prior art and decision

- [slang](https://www.sv-lang.com/) parses, checks and elaborates SystemVerilog.
  Its library and Python bindings offer a later source-level extraction path.
- [Yosys JSON](https://yosyshq.readthedocs.io/projects/yosys/en/v0.55/cmd/write_json.html)
  records hierarchy, bit connections, cell port directions and source attributes.
  Reuse this representation after `proc`, before flattening or technology mapping.
- [Yosys front ends](https://yosyshq.readthedocs.io/projects/yosys/en/latest/cmd/index_frontends.html)
  include `read_slang` in builds that provide it. Do not assume an installed
  Yosys has this command. The initial importer uses the native Verilog reader.
- [CIRCT FIRRTL](https://github.com/llvm/circt/blob/main/docs/Dialects/FIRRTL/RationaleFIRRTL.md)
  provides debug compilation. A later Chisel adapter must retain FIRRTL locations
  and distinguish Scala origins from emitted RTL locations.
- [GHDL synthesis](https://ghdl.github.io/ghdl/using/Synthesis.html) and its
  [Yosys plugin](https://github.com/ghdl/ghdl-yosys-plugin) provide a VHDL route.
  Synthesis support does not establish mixed-language simulation support.

## Architecture

Add `rvw query build-hdl --top MODULE --out DB FILE...`. Use the existing query
reader and schema tables. Keep the importer under `rvw.query`. No core names
belong in it. Each module instance gets a component row. Each named net gets a
signal row. Preserve aliases with directed edges through shared bit identities.
Create internal bit signals for lowered cell ports. Named vector nodes can join
disjoint bit slices. Treat these paths as conservative signal-level reachability.
Module ports connect parent bits to child bits in the declared direction.
Lowered builtin cells connect every input bit to each output bit. This is a
conservative whole-cell dependency graph, not a bit-exact functional cone.
Mark select edges separately. Preserve flip-flop state boundaries. Reject unknown
cells, memories, inouts and blackboxes until their semantics are implemented.
Never publish a partial database after a tool or import error.

Use the canonical Scala schema as the source for a packaged SQL schema. A test
must compare both definitions. Publish a private SQLite sibling with atomic
rename. Record frontend, tool version, input hashes and graph limits in metadata.
Mark every semantic diff key incomplete. A navigation database cannot establish
hardware identity.

## Interfaces and C1–C9

C6 owns this increment. Keep root component path empty and omit the top name
from signal paths. Use `data` and `sel` edge kinds. Source locations refer to
original HDL, not Scala. `spinal_path` repeats the HDL path for reader compatibility.
Unsupported typed diff keys start with `$incomplete:`.
C8 requires captured inputs, including include files, before compilation. The
first slice refuses include directives and file-reading system tasks; users
supply explicit self-contained translation units. Record tool identity but do
not claim transitive tool identity. Capture declarations for `where` navigation.
C1–C5 and C9 remain unchanged. This database proves no runtime behavior. C7 uses
existing query tools on the same file; a new MCP build entry is a later phase.

## Acceptance tests

1. Tests must fail before the importer exists.
2. Use a small hierarchical SV design with repeated instances, constants,
   aliases, slices, muxes and registers. Check drivers, loads, path and locations.
3. Compare query reachability with an independent traversal of Yosys JSON bits.
   This checks translation fidelity, not independent synthesis correctness.
4. Build a pinned open core from a read-only `ref/` checkout. Use SERV `serv_top` for
   the native Verilog subset. Its register-file interface remains external. Also use an Ibex SV block. Record full-core Ibex
   support as pending until slang integration and all dependencies are tested.
5. Refuse unsupported cells, unresolved modules, inouts, memories and includes.
   A failed rebuild must leave an existing database intact.
6. Compare packaged SQL with the current Scala schema. Run existing query tests.

## Risks and limits

Yosys lowers procedural syntax. Assignment locations can describe a whole
process. Aliases can lose declaration locations. Whole-cell edges can overstate
arithmetic dependencies. They must not become proof or CDC signoff evidence.
Register stage counts can include multiple aliases of the same state.
Named constant nets have no variable drivers. Synthesis can remove unobservable
logic; avoid optimization passes. No source text reconstruction is promised.

## Phases

1. Native Yosys subset, database writer, CLI and oracle tests.
2. slang elaboration for a complete Ibex configuration, include capture,
   source statement precision, memory ports and explicit IP model contracts.
   Done: `--frontend slang` (yosys-slang netlist plus JSON AST parameters and
   types), directory capture for includes, memory ports, Ibex `ibex_core`.
   Open: statement-level precision, exact edges, IP model contracts.
3. Chisel FIRRTL/CIRCT adapter with source maps, configuration identity and
   tests against emitted RTL. Reject unresolved extern modules.
4. GHDL adapter with source locations, memory semantics and a tested VHDL core.
   Specify scheduling and foreign interfaces separately from static queries.
5. Source debug and generated checks remain separate deliverables under #26.

Follow-ups: [full SV and slang](https://github.com/riscPrint/risc-v-workstation/issues/370),
[VHDL and GHDL](https://github.com/riscPrint/risc-v-workstation/issues/371).
[Chisel and CIRCT](https://github.com/riscPrint/risc-v-workstation/issues/372).
