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

## Bootstrap decision

The first instruction is `csrw mhpmevent3, zero`, encoded as `0x32301073`.
The trap cause is 2. CSR address `0x323` resolves to `mhpmevent3` through
the shared catalog. The catalog defines it under Sm, not Zihpm. Disabling
HPM event counting does not remove this CSR from the declared Sm contract.
The project's `csr-contract.json` binds this absence to `rv32imasu` and
`platform32.json`. The plan reports one `missing-required` finding. This
model covers only the first blocked CSR. It is not a full CSR inventory.

At the pinned source, `PerformanceCounterPlugin.scala` supplies dummy
zero-valued counter and event-selector accesses. `Param.scala` adds this
plugin only when `extension.withPerformanceCounters` is true. The selected
`VexiiTop.param` enables A, S and U but does not enable performance counters.
The measured illegal access agrees with this configuration.

Decision: retain one declared-profile CSR compatibility finding, affecting
270 test cases. Do not label these as 270 independent core defects. Do not
remove bootstrap writes or lower the Sm version to earn a pass. A profile
that enables the upstream counter plugin would be a different RTL target
and needs its own measurements. No core source is changed here.

The privileged specification permits unused counters and event selectors
to read as zero. That option does not permit an illegal-instruction trap
on these standard accesses. See [machine counters](https://docs.riscv.org/reference/isa/priv/machine.html).
The existing 270-case campaign and 37 representative Spike differences
remain the suite evidence. A fresh full campaign reports 270 C1 failures and 270 strict Spike mismatches.
All first traps remain `0x32301073`. Zero complete matches were earned.
See `bootstrap-review.json` for each ELF hash, C2 hash and first difference.
The run used one persistent worker with fresh simulation instances.
The comparison uses zero masks and zero synchronization.
It ran after the worktree refresh on a stable source checkout.
