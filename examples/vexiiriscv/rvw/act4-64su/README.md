# RV64 supervisor ACT4 profile

This profile selects RV64IMA, M/S/U and Sv39 with standard Sm boot.
The PMP granularity is 16 bytes. NA4 is absent. The core has eight usable
PMP entries. The CSR selection records the absent `mhpmevent3` CSR.
ACT4 requires it under the declared Sm profile. This compatibility finding
must stay visible. The RV32 supervisor profile has the same absence.

Native results: 302 built and 302 run. All 302 fail in the standard boot
before the symbol-delimited test body. Every first trap is cause 2 on a
write to `mhpmevent3` (CSR 0x323). No complete strict Spike match is claimed.
This is one profile bootstrap compatibility finding across 302 cases.
The project omits the counter plugin that supplies this CSR. The catalog
records its absence as a declared Sm compatibility finding. This does not
establish a defect in the upstream core with that plugin enabled.

See [per-test hashes and first traps](results.json) and
[the minimal write program](missing-event-csr.S). The 16-byte PMP profile
uses no NA4 region. The preliminary 4-byte profile's 307 ELFs are excluded.
No bootstrap access is removed or waived.

Use `rvw regress act4-build --profile rvw/act4-64su/profile.json --checkout
"$ACT4_CHECKOUT" --out rvw/out/act4-rv64`. Select `rvw64.toml` and suite
`act4-rv64`. Compare with `rvw/platform64.json`. Device-model interrupts
in Sail do not establish DUT device support.

Run-output JSON files with `summary_only` contain historical counts only.
They are not inputs to `rvw plan`, `rvw evidence`, or coverage merging.
Regenerate full records outside the repository before using those tools.
