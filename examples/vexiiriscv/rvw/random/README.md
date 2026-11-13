# Native random stimulus

The profile is generated from `../platform.json` with
`scripts/riscv-dv-project.py`. See the VexRiscv random example and
`scripts/riscv-dv/README.md` for setup. Select the private checkout through the
project's `core.source_repo`. Set `core.lock` and `RVW_VEX_LOCK` to `vex-dv`.
Set `VEXIIRISCV` to that checkout. Use `nice -n 10`.

```sh
rvw --project examples/vexiiriscv/rvw.toml regress random \
  --settings examples/vexiiriscv/rvw/random/random.toml \
  --seed-base 49 --seeds 1 --out NEW_DIRECTORY --json
```

## Measured results

On 2026-11-13, seed 48 passed C1 and matched all 125 retired instructions with
Spike. Seed 49, with software scratch initialization, passed C1 and matched all
113 retired instructions. Both comparisons were strict, complete and nonempty.
Neither used masks or synchronization. Neither trace has CSR snapshots.
The configuration is RV32IM at core revision `9f70315d`.

The [measurement record](native-2026-11-13.json) retains both results and hashes.
Raw artifacts remain at its recorded paths. The tools worktree was dirty.
These bounded results do not establish full ISA, CSR-state, formal, physical or
C4 acceptance. The extra instruction initializes `mscratch` before the GPR setup.
It fixes the undefined-input mismatch found by the VexRiscv campaign.

Artifact paths in the JSON are relative to the workstation root.
