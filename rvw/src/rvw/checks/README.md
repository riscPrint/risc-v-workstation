# Project check generation

Run `rvw checks generate --all --project PATH --out out/checks`.
MCP: `checks_generate`, with `project`, `out` and optional `manifest`.
The default manifest is `checks.generate.json` beside `rvw.toml`.
It has schema `rvw.check-generation/1`. Optional keys `streams`, `buses`,
`csrs`, `queues`, and `power` name files relative to the manifest.

- `streams`: a property-library JSON document with a `properties` list.
- `buses`: a captured SpinalDB database.
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

The library also retains ROB, credit and allocation-pool conservation templates.
Use `rvw formal template KIND` or declare the six new rule kinds in project data.

## Decisions

Reuse the existing generators. Keep signal names in project data. Report source
emission separately from instance binding. Do not infer protocol or reset semantics.

## Limits

This command does not compile a design or run a solver. Declared ports have not
been checked against RTL widths. Stream and power automatic binding remain open.
The bus generators report channel safety separately from transaction scoreboards.
