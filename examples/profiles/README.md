# Pinned profile inventory

`source-index.json` records 273 imported and inherited requirements from
riscv-profiles revision `e030b70992447784ad9081045d47ce6e278f381e`.
It includes all four selected RVA23/RVB23 U64/S64 profiles. Source hashes,
URLs and line spans identify the original text. The index contains no proof
results. Its checker and test mappings remain unassigned.

Set `RISCV_PROFILES` to that source checkout. Set `RVW_ISA_MANIFEST` to the
core's ISA declaration. Run:

Historical profile catalog schema example (`examples/profiles/profiles.example.json`; `formal profiles` catalog CLI was trimmed).

The command writes a source index and per-document catalogs. Assign and review
checker/test mappings before catalog adoption. Declare base or standalone
clause implementation with `declarations` in the project plan. Missing
declarations remain missing. A declaration is not proof evidence.

The index covers imported profile source clauses. It does not qualify an ISA,
core, compiler or reference model. It does not provide complete ISA, debug or
platform specification catalogs.
