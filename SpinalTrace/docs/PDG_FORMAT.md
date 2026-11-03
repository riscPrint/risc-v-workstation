# SpinalTrace PDG format (`W/spinaltrace/pdg.json`)

SpinalTrace writes the **ChiselTrace `PDGSpec` JSON** (`spinaltrace-rs/src/pdg_spec.rs`, unchanged field
names) so the ChiselTrace engine and GUI can read it. A few optional fields are added; a ChiselTrace PDG is
still a valid SpinalTrace PDG and the engine falls back to ChiselTrace behaviour when they are absent.

```json
{
  "vertices":   [ PDGSpecNode, ... ],
  "edges":      [ { "from": 9, "to": 12, "kind": "Data", "clocked": true, "condition": null }, ... ],
  "predicates": [ { "name": "when_Gcd_l19", "file": "...", "line": 19, "char": 1, "kind": "DataDefinition", ... } ],
  "cfg":        [ { "stmtRef": 0 }, { "stmtRef": 8, "predStmtRef": 0, "trueBranch": [...], "falseBranch": [...] } ],
  "spinaltrace": { ... }            // extension, see below
}
```

## Signals and symbols

* One **symbol per Spinal `BaseType`** = `HglNaming.rtlPath(bt)` (SpinalWaves contract): instance path
  from the toplevel (toplevel excluded) plus the final RTL name, e.g. `io_result`, `mid.stage`,
  `mid.leaf.io_y`. It is also the VCD path below the extra scopes (`TOP <Toplevel>`).
* Spinal's netlist is already flattened to leaf signals (`io_a`, `regs_2`), so ChiselTrace's compound
  signal / connect-ID / flip machinery is not needed. A parent's `sub.io.x := ...` assigns the child's IO
  BaseType, so it *provides* `sub.io_x`, which the child reads: the hierarchy links through the same
  symbol, exactly like ChiselTrace's flattened FIRRTL names.
* Memory words: `<instance path>.<mem name>.<index>` (e.g. `mem.3`); memories with more than
  `ExtractOptions.maxMemWords` (4096) words use one coarse symbol `<path>.<mem>`.
* Internal symbols start with `$` and never appear in the VCD: `$condN`, `$switchN`, `$caseN` (control
  flow vertices), `$probeN` (probe vertices), `$instN` (instance declarations).

## Vertices (`PDGSpecNode`)

| field | meaning |
|---|---|
| `file`, `line`, `char` | Source location: first user frame of Spinal's ScalaLocated stack trace (two-pass `debugComponents`), resolved to an absolute path by `spinalwaves.SourceLocator`; frames of `java.*`, `spinal.core`, `spinal.sim`, `spinal.lib` (configurable), `spinaltrace`, `spinalwaves` are skipped. Fallback: Spinal's `genLineComments` string. `char` is SpinalWaves' column (1; the JVM has no columns). |
| `name` | Statement name, conventions below. Not unique (two `connect_x` in the GCD). |
| `kind` | `IO`, `Definition`, `DataDefinition`, `Connection`, `ControlFlow` (ChiselTrace kinds). |
| `clocked` | Assignment takes effect after the clock edge (register, memory write, reset value, clocked assert). |
| `modulePath` | Instance path of the component *containing the statement* (`["mid","leaf"]`). |
| `relatedSignal` | `{signalPath, fieldPath}` = `HglNaming.hglPath(target)` for user signals (used for typed values); `null` for compiler-generated signals. |
| `assignsTo` | Symbol this statement provides (see above); `null` for sinks and declarations. |
| `isChiselStatement` | `true` for statements on user-named signals and user statements (`when`, `switch`, asserts...); `false` for Spinal's anonymous `_zz_*`, its auto-named `when_<File>_l<n>` / `switch_<File>_l<n>` conditions, signals named by SpinalTrace, and probe vertices. Used by the source-statement grouping (`conversion.rs`) to pick the group's representative. |
| `condition` | Vertex condition `{probeName: [...], probeValue: [...]}`: the statement only becomes the provider of `assignsTo` when all named signals hold the given values in that cycle (used for dynamic Vec writes, memory writes, read enables). |
| `assignDelay` | `1` for synchronous memory reads (`readSync`, `readWriteSync`): the data appears one cycle after the statement is activated. |
| `assignRange` | **Extension.** Partial assignment key: `"3"` (`x(3) := ...`), `"7:4"` (`x(7 downto 4) := ...`), `"dyn"` (dynamic bit/range index). Absent = full assignment. |

### Vertex naming conventions

`<rel>` is the target's name relative to the statement's component (`x`, `io_result`, or `leaf.io_x`
for a parent assigning a child IO).

| name | kind | Spinal construct | ChiselTrace analogue |
|---|---|---|---|
| `input_<n>` | IO | toplevel input port (provides it) | `input_` |
| `output_<n>` | IO | toplevel output port (sink, Data dependency on the port) | `output_` |
| `input_<n>` / `output_<n>` | Definition | IO port of a child component (declaration only, no `assignsTo`) | non-main IO as Definition |
| `defwire_<rel>` | Definition | combinational signal declaration (`UInt(8 bits)`, `Bool()`) | `defwire_` |
| `defnode_<rel>` | DataDefinition | combinational signal declared **and** fully assigned once on the same line (`val t = a + b`), i.e. a Chisel `node`; the declaration vertex is folded into it | `defnode_` |
| `connect_<rel>` | Connection | `DataAssignmentStatement` (`:=`), also partial `x(i) :=` | `connect_` |
| `defreg_<rel>` | Definition, clocked | register without init value | `defreg_` (DefRegister) |
| `defreg_<rel>` | DataDefinition, clocked | `InitAssignmentStatement` / `InitialAssignmentStatement` (`init(...)`): reset value, provides the register | `defreg_` (DefRegisterWithReset) |
| `defmem_<mem>.<i>` | Definition, clocked | memory word declaration | `defmem_` |
| `connect_<mem>.<i>` | Connection, clocked | `mem.write` / `readWriteSync` write side, one vertex per word with condition `address == i` (and enable `== 1`) | memory write port |
| `cond_on_[<signals>]` | ControlFlow | `when` / `elsewhen` condition; `<signals>` = leaves of the condition's driver for Spinal's auto-named `when_*` conditions, else the condition signal | `cond_on_[...]` |
| `switch_on_[<value>]` | ControlFlow | `switch(value)` | (new) |
| `case_on_[<value> is <keys>]`, `case_on_[<value> default]` | ControlFlow | one `is(...)` / `default` (Conditional dependency on the switch vertex) | (new) |
| `defnode_probe_<sel>` | DataDefinition | **probe vertex** for a mux select, dynamic Vec/bit/range index, memory address or enable; the user statement has an Index edge to it, it has Data edges to the select's providers | ChiselTrace's inserted `defnode_probe_*` nodes (here no logic is inserted: the probe vertex only exists in the graph) |
| `assert_<File>_l<n>`, `assume_...`, `cover_...` | Connection (sink) | `AssertStatement` (clocked when CLOCKED) | `intrinsic_*` |
| `definstance_<inst>` | Definition | child component instance; every statement of the child has a Declaration dependency on it | `definstance_` |
| `blackbox_<inst>.<port>` | Connection | output of a `BlackBox` (opaque: depends on all non-clock inputs) | ExtModule ports |

Clock-domain plumbing (clock / reset / clock-enable ports and their wiring into children) is not traced,
like ChiselTrace drops `clock` connections. The toplevel reset port does get an `input_reset` vertex.

## Edges (`PDGSpecEdge`)

`from` depends on `to`. Kinds follow ChiselTrace's `matchDependencies` exactly, by the kind of the
provider: Connection / IO → `Data`; DataDefinition → `Data` + `Declaration`; ControlFlow → `Conditional`;
Definition → `Declaration`; dependencies through a probe vertex → `Index`. `clocked` is the dependent
statement's `clocked`.

`condition` on an edge: the dependency only exists in a cycle where the named signals hold the given
values. Used for

* mux inputs: `Mux(sel, a, b)` → edge to `a` with `sel == 1`, edge to `b` with `sel == 0`; nested muxes
  concatenate conditions; `Vec(...)(idx)` reads (`Multiplexer`) → edge to element `i` with `idx == i`;
* memory reads: edge to word `i` with `address == i`.

`probeName` entries are **RTL paths of existing Spinal signals** (relative to the extra scopes), not
`probe_*` signals: the engine watches every signal named in a condition, predicate or case key. The
SpinalTrace naming phase makes sure anonymous selects/indexes get a name (and therefore exist in the VCD).

## Predicates

Each entry is a VCD signal the CFG branches on: `name` = RTL path of the `when` condition or `switch`
value (`when_Gcd_l19`, `io_loadValues`, `io_op`). `predStmtRef` in the CFG indexes this list.
Conditions are 1-bit; switch values may be multi-bit (the engine stores bit strings).

## CFG

Same tree as ChiselTrace: a list of `{stmtRef}` statements in execution order (later assignments to the
same signal in the same cycle win), forks `{stmtRef, predStmtRef, trueBranch, falseBranch}` for `when`.
Spinal's `elsewhen` is a nested `when` in the false branch, exactly as Spinal builds it.
Component order: a component's own statements, then for each child its statements followed by its
`definstance_` statement.

**Extension: switch forks**

```json
{ "stmtRef": 12, "predStmtRef": 2,
  "cases": [ { "keys": [ { "pattern": "01" } ], "branch": [ { "stmtRef": 13 }, ... ] },
             { "keys": [ { "pattern": "1--0" }, { "signal": "mid.key" } ], "branch": [ ... ] } ],
  "defaultBranch": [ ... ] }
```

The predicate holds the switch value; the first case with a matching key is taken, else `defaultBranch`.
A key is a bit pattern (MSB first, width of the value, `-` = don't care, from Spinal `MaskedLiteral`), or
`signal` = another (named) signal whose current value must be equal. Enum keys are encoded with the
enum's final encoding (`binarySequential` by default, `oneHot`, custom...). Chosen over chained boolean
forks because it needs no new `value === key` signals in the design (CONTRACT.md forbids new logic).
The first statement of each branch is the `case_on_[...]` vertex.

## `spinaltrace` metadata (extension)

```json
"spinaltrace": {
  "formatVersion": 1,
  "toplevel": "GCD",
  "extraScopes": ["TOP", "GCD"],
  "clockDomains": [ { "clock": "clk", "reset": "reset", "resetKind": "ASYNC", "resetActiveLow": false,
                      "clockEnable": null, "softReset": null, "registers": 2 } ],
  "warnings": [ "..." ]
}
```

Defaults for the CLI/GUI flags `--top-module`, `--extra-scopes`, `--clock`, `--reset`, `--reset-kind`,
`--reset-active-low` come from here (the clock domain with most registers). `warnings` lists
extraction approximations (multiple clock domains, BlackBoxes, coarse memories, unsupported constructs);
the CLI prints them.

## Dynamic graph (CLI / GUI output)

`spinaltrace-cli dyn-pdg` writes ChiselTrace's `ExportablePDG` (`vertices`, `edges`; snake_case fields)
after grouping netlist statements into source statements by (file, line, timestamp). Extension: each
vertex has `assigns_to` (RTL path) and `sim_data` holds the typed Tywaves value (HGLDD) or, without
HGLDD, the raw VCD value (`"12 (0xc)"`).

Timestamps (as in ChiselTrace): a statement activated in cycle `t` (cycle 0 = before the first rising
edge, cycle `t` ends at rising edge `t+1`) is labelled `t` if clocked and `t-1` if combinational; both
labels mean "the value seen during cycle `t+1`". Reset values applied at t=0 are labelled -1. The GUI
displays `timestamp + 1`.

## Accuracy contract (formatVersion 2)

Extraction writes `accuracy: {status, reasons}` beside `vertices` and `edges`.
The Rust exports and slice JSON use the same field. The GUI shows it above the graph.
`exact` means no known extraction or replay limit applies. `approximate` means the
result can include extra causes or merge source statements. `incomplete` means a
needed cause or its timing can be missing. Incomplete takes priority over approximate.
The status covers the whole design. It is not a proof of the selected dependency path.

All extraction warnings make the result incomplete. Legacy extraction metadata,
missing metadata, missing source locations, unknown sampled values and missing VCD predicates also make it
incomplete. A missing reset signal is an error. Source conversion always reports
approximate because file and line do not identify separate statements on one line.
Dropped probe edges make conversion incomplete. Conversion cannot improve accuracy.
Low-level dynamic exports without replay metadata default to incomplete.

The supported timing subset has one rising-edge clock, with no clock enable or soft
reset. Synchronous and asynchronous primary resets use the existing pre-edge replay
rule. Other domains, falling edges, enables and soft resets report incomplete.
A clock override does not remove these limits.

Memory attribution supports bounded, equal-width, unmasked synchronous writes and
asynchronous or synchronous reads. Write masks, mixed-width ports, coarse memories
(above `maxMemWords`, default 4096), and asynchronous writes report incomplete.
Dynamic partial writes report incomplete: only 16 providers survive, and signal
criteria select the latest provider. Fixed partial writes report approximate because
overlapping ranges retain conservative providers and signal criteria select one.

Unsupported switch keys can omit branches and report incomplete. Anonymous control
expressions conservatively include branches and report incomplete. Formal expressions
and analog/inout signals have no supported attribution semantics. They report incomplete
when found. Unknown source causes remain explicit in the reasons.

Disabling replay of a reset recorded in the design reports incomplete. Data-only
traces also report incomplete because they omit control and index causes.
