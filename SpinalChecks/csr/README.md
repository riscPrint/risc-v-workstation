# CSR generation

Run `rvw formal csr --model project-csr.json --out generated`.
The input uses `rvw.csr/1`. `scratch.json` is a starting example for standard
M/S scratch registers. Reset values are project choices, not spec defaults.
Copy the file into the core project. Add its implemented and absent CSRs.
This example is not the complete privileged CSR description.

Each CSR has a unique `name`, numeric `address`, `reset`, minimum `privilege`,
and optional `present` and `read_only` flags. Each field has `lsb`, `width`,
and `access` with explicit U/S/M policies: RW, RO, WARL, WLRL, WPRI.
Unspecified bits preserve their reset values. RO fields ignore writes.
`read_only` CSRs trap on writes. CSR addresses in 0xC00..0xFFF also trap on writes.
WARL/WLRL fields require `legal` values that include reset.
WARL uses an optional `legalize` table, and preserves the old value otherwise.
WLRL uses an explicit reject-illegal policy. This is a project policy.
Field `effect` can be `none`, `w1c`, or `read_clear`.
Writes win over read-clear. Denied accesses preserve software state.
Hardware clear then set takes priority over software updates.

The generated `rvw_csr` Verilog module checks state, trap and granted read data.
A project wrapper must instantiate it beside the DUT. Connect `valid` only for
completed CSR transactions. `rd` and `wr` are architectural read/write enables:
CSRRW with rd=x0 suppresses read; CSRRS/CSRRC with rs1=x0 suppress write.
`data` is the replacement value after CSR instruction set/clear processing.
`rdata` is the pre-update response. `state_NAME` must observe actual DUT storage.
`hw_set` and `hw_clear` apply to the addressed CSR on that transaction only.
This version cannot represent autonomous updates between accesses or aliases.
The first sampled edge must assert reset. Do not tie DUT storage to the model.
A generated SBY file is available when `binding` declares `top` and a `sources`
list relative to the model file. That wrapper must instantiate `rvw_csr`.
Run `sby -f csr.sby` in the output directory. No proof runs during generation.

Each generated assembly file has `_start`, an illegal-instruction trap handler,
and a `tohost` result. Link it with the project's memory layout and entry address.
Run its ELF through the project's C1 adapter with an RVFI trace, then use
`rvw cosim check` with that ELF, trace and the project's Spike platform.
The program checks M-mode reads and absent-CSR traps. Set `assembly_safe` only
for deterministic CSRs that can be written without changing execution state.
Those programs also check reset and zero/all-one/reset writes. This version does
not generate privilege transitions, aliases, counter timing, or full compliance.
`coverage.json` uses the existing `rvw cov functional` group format.
Generation is not execution or coverage evidence.

## Decisions

Keep all DUT bindings in project files. Use one independent expected state per
CSR. Never initialize it from observed DUT storage.

## Pinned CSR catalog and project overrides

The base catalog has 416 CSR definitions and 1,395 fields from
RISC-V Unified Database revision
`176fc36018be56925061566447a656b93eba0ddb`. Each row keeps the original definition,
source path, source SHA-256 and copyright notices. Field aliases, extension
conditions, reset expressions and WARL legalization IDL remain data.
The BSD-3-Clause-Clear license is in `CSR_CATALOG_LICENSE.txt` beside the data.
Regenerate from that external source checkout with:

```sh
uv run --no-project --with PyYAML==6.0.3 python SpinalChecks/csr/import-udb.py UDB_CHECKOUT rvw/src/rvw/formal/csr_catalog.json
```

Use `rvw.csr-selection/1` with the existing `--model` option.
`examples/vexriscv/csr.json` selects the example's M-only scratch register and
absent supervisor scratch register. Each selected CSR has a project reset and
explicit field access policies. Catalog field names determine bit positions.
Project `legal`, `legalize` and `effect` overrides use the existing model rules.
Extension predicates and IDL are not evaluated. Select only implemented fields.
Use a full `rvw.csr/1` model for project-specific or read-only-zero fields whose
names are not in the source data. Generation refuses aliases, hypervisor/debug
access models and unsupported field locations. It never converts these to RW.

The 26 recorded AIA layout gaps are supplemented from RISC-V AIA revision
`9507866427961d4ec2d2400ea875103b2a09520b`. The combined catalog has 442
registers and 1,974 fields. Supplemental rows retain source hashes, attribution,
license, bit positions and alias facts. The AIA supplement uses CC-BY-4.0;
`AIA_CATALOG_LICENSE.txt` supplies the license. The base UDB data remains unchanged.
Regenerate the supplement from the pinned external AIA checkout with:

```sh
python3 SpinalChecks/csr/import-aia.py AIA_CHECKOUT SpinalChecks/csr/catalog-gaps.json rvw/src/rvw/formal/csr_aia_catalog.json
```

`catalog-gaps.json` retains the original 26 rows as resolved field definitions.
This is field-layout coverage, not AIA behavior coverage. Conditional aliases,
interrupt-file claims, virtual interrupt state and privilege sequences still
need execution models. Selections that require an interrupt environment are
refused. No IDL or interrupt semantics are inferred from field positions.
The VexRiscv project's optional bindings are described in its README. Catalog
selection alone is neither a DUT binding nor a compliance result.
