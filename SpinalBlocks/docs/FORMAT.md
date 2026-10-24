# SpinalBlocks diagram format (version 1)

The Scala extractor writes one JSON document per design, plain (`.json`) or gzipped (`.json.gz`).
The engine (`engine/`, `loadDesign`) reads either.

```jsonc
{
  "format": "spinalblocks", "version": 1,
  "top": "BoomSimTop",                  // module name of the toplevel
  "generated": "2026-10-20T12:00:00Z",
  "modules": { "<moduleName>": Module, ... }   // one entry per emitted Verilog module (definitionName)
}
```

## Module

One diagram. Instances of the same module share it.

```jsonc
{
  "name": "Gcd",                       // Verilog module name (Spinal definitionName)
  "className": "spinalwaves.examples.Gcd",
  "loc": Loc | null,                   // the class definition (first line of its constructor)
  "instanceCount": 3,                  // how many instances of this module exist in the whole design
  "blackbox": false,                   // a Spinal BlackBox: ports only
  "ports":     [Port, ...],            // this module's own IO, in declaration order
  "instances": [Instance, ...],        // child components
  "nodes":     [Node, ...],            // logic blocks (areas, registers, combinational logic, memories)
  "nets":      [Net, ...],
  "fsms":      [Fsm, ...]               // state machines (optional)
}
```

## Loc

```jsonc
{ "file": "/abs/path/Gcd.scala", "line": 12 }
```

`file` is absolute when the source was found under the configured source roots, otherwise a bare
file name. Locs are `null` when the design was elaborated without location tracking.

## Port

```jsonc
{
  "name": "io_result",                 // Verilog name
  "dir": "in" | "out" | "inout",
  "width": 16,                         // bits
  "type": "UInt",                      // Spinal type: Bool, Bits, UInt, SInt, enum name, ...
  "group": "io_mem_a",                 // innermost enclosing Bundle, or "" (clk, reset); used to fold ports
  "groups": ["io", "io_mem", "io_mem_a"],  // all enclosing Bundles, outermost first
  "loc": Loc | null
}
```

## Instance

```jsonc
{
  "id": "inst:gcd_0",                  // unique inside the module
  "name": "gcd_0",                     // instance name
  "module": "Gcd",                     // key into "modules"
  "parent": "area:core_logic" | null,  // Node id of the enclosing Area, or null for the module body
  "loc": Loc | null                    // where the instance is created
}
```

The instance's ports are the child module's `ports`.

## Node

Logic inside the module, grouped the Spinal way: by `Area`. Areas nest (a `StateMachine` or a
spinal.lib `Composite` is an area too). An area that contains other areas or instances is a
*compound* node; its own signals are then in a leaf child node with `kind: "logic"` and
`id` = `<area id>/logic`.

Signals in no area are grouped as follows:

* the fields of one internal Bundle/Vec (`val req = Stream(...)`) form one node;
* anonymous registers (`_zz_*`) form one node per source line that created them, named like
  Spinal's own temporaries: `rob_l338` (Rob.scala line 338);
* loop copies of a named signal (`x_0`, `x_1`, ...) form one node named `x`, `rob_*_valid` style;
* any other named signal is its own node.

Signals that are folded into nets instead of becoming nodes: compiler temporaries (`_zz_*`,
`when_<File>_l<n>`), constants, plain wires (`a := b`, unconditional, outside any area), outputs that
are not registers, and child inputs read back by the parent.

```jsonc
{
  "id": "area:fsm" | "sig:x" | "area:fsm/logic" | "mem:ram",
  "name": "fsm",                       // display name
  "kind": "area" | "reg" | "comb" | "mixed" | "mem" | "logic",
  "parent": "area:outer" | null,       // enclosing area node id
  "compound": true | false,            // true when other nodes or instances have this node as parent
  "className": "spinal.lib.fsm.StateMachine" | null,   // Area subclass, if any
  "loc": Loc | null,
  "signals": [ { "name": "x", "width": 16, "type": "UInt", "reg": true, "loc": Loc | null }, ... ],
  "regCount": 2, "combCount": 0        // over `signals`
}
```

`kind`: `area` for an Area (leaf or compound), `logic` for a compound area's own signals, `mem` for a
`Mem` outside any area, else `reg` when all signals are registers, `comb` when none are, `mixed`
otherwise. Memories in an area are listed in its `signals` with `type: "Mem[<words>]"`.

A registered output port gets its own node (`sig:<port>`), wired to the port.

## Net

A directed connection from one driver endpoint to one or more sink endpoints.

```jsonc
{
  "id": "n12",
  "name": "x",                         // the signal carried (Verilog name of the source signal)
  "width": 16,
  "via": ["tmp_a", "io_out_w"],        // named pure wires the connection passes through (may be empty)
  "control": false,                    // true when every sink reads it only as a when/switch condition or mux select
  "clock": false,                      // a clock, reset or clock enable
  "from": Endpoint,
  "to":   [Endpoint, ...]
}
```

## Endpoint

```jsonc
{ "kind": "port", "port": "io_a" }                         // this module's port (input as driver, output as sink)
{ "kind": "inst", "id": "inst:gcd_0", "port": "io_a" }     // a child instance's port
{ "kind": "node", "id": "sig:x" }                          // a leaf logic node
```

A memory read is drawn as memory node -> reader; the address and enable feed the memory node.
Endpoints always reference leaf nodes. The viewer redirects them to the nearest visible ancestor
when areas are collapsed. A net never has the same endpoint on both ends.

## State machines

`Module.fsms` lists the module's state machines: every `spinal.lib.fsm.StateMachine`, and every
register of a `SpinalEnum` type whose assignments are enum constants.

```jsonc
{
  "id": "fsm:ctrl_fsm",
  "name": "ctrl_fsm",                  // the StateMachine area, or the register
  "node": "area:ctrl_fsm" | null,      // logic node holding the register
  "register": "ctrl_fsm_stateReg",
  "kind": "statemachine" | "enum",
  "loc": Loc | null,
  "states": [ { "name": "idle", "loc": Loc | null }, ... ],   // enum order; StateMachine's internal BOOT state is left out
  "reset": "idle" | null,              // StateMachine entry state, or the register's init value
  "transitions": [
    {
      "from": "idle" | null,           // null: the assignment is not inside a per-state branch
      "to": "run" | null,              // null: the next state is not a constant (unresolved)
      "condition": "fifo.io_pop_valid" | null,   // other enclosing when/switch conditions, as text
      "comment": null,                 // a `//` comment on the source line of the goto/assignment
      "loc": Loc | null
    }
  ]
}
```

A state is *dead* when it has no outgoing transition and *unused* when it has no transition at all;
the viewer derives both.
