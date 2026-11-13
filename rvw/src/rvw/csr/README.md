# Shared register metadata

Run `rvw csr show mstatus --json` or MCP `csr_describe`.
These calls read metadata. They do not execute or prove a CSR check.

`rvw.csr.catalog` owns the data API:

- `catalog()` returns the pinned base and AIA supplement with source notices.
- `definition(name_or_number)` returns fields, aliases and raw WARL IDL.
- `address(name_or_number)` resolves a name or preserves an explicit project number.
- `load_model(path)` reads project data and resolves catalog selections. Consumers validate their own schemas.
- `materialize(selection)` applies the existing project reset and field overrides.
- `peripheral_registers(region)` projects the existing project MMIO map.

The pinned files stay under `rvw/formal` for compatibility with the import scripts.
The old `rvw.formal.csr_catalog` imports forward to this API.
Architectural CSR numbers and MMIO byte addresses stay in separate address spaces.
The MMIO subset declares whole-word fields. It does not declare aliases or WARL.
The API retains actions and project policies. It does not evaluate upstream IDL.
Formal artifacts, co-simulation capture/masks, UVM RAL and SoC exports use this API.

## Decisions

Share data only. Keep checker and formatter logic in its existing package.
Keep project reset, legal values and legalization choices explicit.
Preserve refusals for unsupported alias and execution semantics.
The fast catalog guard rejects another pinned catalog or private name/address table.
