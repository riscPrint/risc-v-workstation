# Project check generation

Run `rvw checks generate --all --project PATH --out out/checks`.
MCP: `checks_generate`, with `project`, `out` and optional `manifest`.
The default manifest is `checks.generate.json` beside `rvw.toml`.
It has schema `rvw.check-generation/1`. Optional keys `streams`, `buses`,
`csrs`, `queues`, and `power` name inputs relative to the manifest. Use
`--json` for JSON errors as well as successful summaries.

- `streams`: a property-library JSON document with a `properties` list.
- `buses`: a captured SpinalDB database, or an object with `database`, optional
  AXI tracker `depth` and optional write history `max_beats`. Defaults are 4
  pending descriptors and 256 beats. Capacity assertions are instrumentation
  limits. The per-instance report states which transaction checks bind.
  `type_report` can name a matching SpinalChecks report to resolve ambiguous
  TileLink `Bus` classes.
- `csrs`: a CSR model or catalog selection.
- `queues`: an `rvw.micro-checks/1` document.
- `power`: an `rvw.power-intent/1` document.

The output has one directory per supplied kind and `result.json` with schema
`rvw.check-generation-summary/1`. Missing data and bindings retain a reason.
Declared microarchitecture and database bus instance binds count as generated.
CSR sources without a project wrapper, power modules without instance binds,
and stream snippets without a containing module remain `unbound`.
Exit 3 means no bound checks. Exit 0 means some checks were generated. Neither
exit establishes a proof. Existing output directories are refused.

## Bound Stream/Flow and UPF inputs

The `streams` entry can be an object with `database`, `report` and optional
`contracts` file paths. The report uses `rvw.checks/1`. Contracts map channel
instance paths to reviewed properties. A Stream requires `stable=true`.
A Flow requires explicit `max_value` or per-field `max_values` bounds.
The generator resolves instance-local ports, widths and clock/reset metadata.
It emits procedural monitors and instance binds. Missing contracts, unresolved
controls and unsupported channels retain their reasons. Use a SystemVerilog
frontend with bind support. No property is inferred from a signal-name suffix.

The `power` entry can be an object with UPF `source` and `bindings` paths.
It emits the existing literal isolation, retention, supply-table and power-switch
monitors with project-declared instance bindings. Unmonitored domains stay
listed. Plain stream property files and power-intent JSON files still emit
sources as `unbound` when no instance binding is supplied.

For example:

```json
{
  "schema": "rvw.check-generation/1",
  "streams": {"database": "design.db", "report": "checks.json", "contracts": "streams.json"},
  "buses": "design.db",
  "csrs": "csrs.json",
  "queues": "rules.json",
  "power": {"source": "power.upf", "bindings": "power-bindings.json"}
}
```

## Project microarchitecture rules

The queue document has `schema=rvw.micro-checks/1`, `top` and a `rules` list.
Each rule has a unique `id`, `kind`, optional `width` and `entries`, and `ports`.
Port keys name the monitor interface. Values name project RTL signals.
Every rule requires `clk` and active-high `reset`.

| Kind | Ports and contract |
|---|---|
| `fifo_order` | `push`, `pop`, `push_data`, `pop_data`. Accepted events; initially empty, no empty bypass. Full simultaneous pop/push is allowed. |
| `pipeline` | `valid`, `ready`, `payload`. Valid and all payload bits remain stable during stalls. |
| `mutex` | `grants`. At most one bit set. |
| `arbiter` | `grants`, `requests`, `enabled`. Grants are one-hot and requested. Each enabled request waits at most `bound` cycles, default 8. This is bounded fairness. |
| `age_matrix` | `valid`, packed row-major `older`. Live entries form a strict total order. It checks consistency, not temporal allocation order. |
| `store_forward` | `load_fire`, `forwarded`, `valid`, `older`, `address_match`, `selected`, `load_data`, packed `store_data`. Higher slot indices are younger. The highest eligible slot must supply the full data unit. Byte merging needs separate per-byte instances. |

The project document also accepts these existing resource rules:

| Kind | Ports beyond `clk` and `reset` |
|---|---|
| `rob`, `credit` | `count`, `push`, `pop`. One accepted increment/decrement per cycle. |
| `allocation_pool` | `live`, `alloc0_valid`, `alloc1_valid`, `free0_valid`, `free1_valid`, `alloc0`, `alloc1`, `free0`, `free1`. Independent expected ownership. |
| `freelist_conservation` | Allocation-pool ports plus `free_bits`. Free and live masks partition literal `usable` tags. |
| `freelist` | `free_bits`, `allocated`. Legacy disjointness check only. |
| `cam_match` | `active`, `require_match`, `match_bits`. At most one match; optional required hit. |
| `counter_bounds` | `active`, `value`. Inclusive unsigned bound `entries`. |

Ownership rules accept literal `initial_live`, default zero. The stronger
free-list rule also accepts literal `usable`, default all entries. Initial
ownership must be a subset of usable tags. Release precedes allocation on the
same edge. These are project declarations. The generator does not infer reset
ownership or multi-entry recovery from a core's implementation.
The overall report lists missing bindings directly in `unbound`. A partial
transaction binding cannot make the overall result complete.

## Decisions

Reuse the existing generators. Keep signal names in project data. Report source
emission separately from instance binding. Do not infer protocol or reset semantics.

## Limits

This command does not compile a design or run a solver. Stream ports and widths
come from the captured database. Microarchitecture ports remain project
declarations. The bus generators report channel safety separately from
transaction scoreboards. Physical power and analog behavior are not modeled.
