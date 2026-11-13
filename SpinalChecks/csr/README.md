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
