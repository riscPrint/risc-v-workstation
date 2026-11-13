# ACT4 supervisor profile

This profile selects all applicable ACT4 tests for RV32IMA, M/S/U and Sv32.
It uses the standard Sm bootstrap. It does not replace that bootstrap to
bypass unsupported CSR accesses. The project declares 9 ASID bits, eight
usable PMP entries, 32 physical address bits and no program-controlled IRQ
devices. Sail-only devices supply the upstream signature model. They do
not add devices to the DUT.

## Build and run

Use ACT4 revision `56d40ab301dba23dd3104c17bd969afbaaea1931`, Sail 0.15
and RISC-V GCC. See [the instruction profile](../act4/README.md) for setup.
Run these commands from `examples/vexiiriscv`:

```sh
rvw regress plan --act4 rvw/act4-supervisor/profile.json --json
rvw regress act4-build --profile rvw/act4-supervisor/profile.json \
  --checkout "$ACT4_CHECKOUT" --out rvw/out/act4-supervisor
rvw regress run --suite act4-supervisor --rvfi-trace --out /tmp/act4-supervisor-run
rvw regress cosim /tmp/act4-supervisor-run --platform rvw/platform32.json
```

The build manifest binds the whole ELF set before suite filters apply.
The ELF signature checks use the Sail reference signatures. A build is
not a DUT pass. Failed C1 runs remain failed in the regression comparison.
Use `rvw cosim check --strict` on a failed trace to inspect its first
reference difference.

## Measured result

On 2026-11-13, 270 ELFs built and ran. This includes 201 tests from the
privileged directories and 69 instruction tests. C1 reported 0 pass,
270 fail and 0 inconclusive. All 270 first trap events report illegal
instruction `0x32301073`, the write to mhpmevent3 in the standard boot.
None retired the `rvtest_code_begin` instruction or any instruction in
`[rvtest_code_begin, rvtest_code_end)`. The privileged test bodies remain
unqualified.

One strict Spike comparison from each of the 37 test groups confirms the
same first difference. These are first-difference results, not complete
trace matches. No synchronization or output mask was used. The exact
per-group built/run/pass/fail/finding counts, per-test ELF hashes, first
traps and representative comparisons are in `observations.json`.

The failure is a core compatibility finding under the selected ACT4 Sm
scaffold. It is not a proved hardware defect. The exact core and firmware
CSR contract remains open. No result is waived. No core source was changed.
`../act4/missing-boot-csr.S`, built with `CSR_ADDR=0x323`, reproduces the
trap. On the same supervisor profile, the 49 riscv-tests pass and have
complete strict Spike matches. The MEPC write-1 control also passes and
matches Spike. These controls do not qualify the blocked ACT4 tests.

The separate instruction profile uses a reduced boot. Its 58 passing
instruction tests do not establish privileged compatibility. These results
come from native RTL simulation. They are not physical hardware results
or architectural certification.
