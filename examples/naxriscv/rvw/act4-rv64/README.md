# RV64 ACT4 instruction profile

This profile uses the pinned ACT4 revision and a machine-mode bootstrap.
It selects I, M, Zmmul, Zaamo, Zalrsc, Zicsr and Zifencei at XLEN 64.
It reuses the RV32 profile's linker and reduced CSR bootstrap.
It does not qualify standard Sm, S/U execution or Sv39 translation.

| Target config | Built | C1 pass | Complete strict Spike match | Synchronizations |
|---|---:|---:|---:|---:|
| `rv64ima` | 98 | 98 | 98 | 0 |
| `rv64imasu` | 98 | 98 | 98 | 0 |

Each set has I 51, M 13, Zaamo 18, Zalrsc 4, Zicsr 6, Zifencei 1 and
Zmmul 5 cases. Both comparisons use no output masks.
The upstream core source is unchanged. These are instruction results on
two configs. They are not full-core or privileged-mode qualification.

A fresh build from this profile has the same load segments, entry points
and tohost addresses for all 98 programs. Debug metadata changes the ELF
file hashes. The native results retain their original ELF receipts.

From the workstation root, use the private core and lock settings in the
project README. Set `ACT4_CHECKOUT` to the pinned ACT4 checkout.
Set `RUN_ROOT` to a directory outside Git.

```sh
export NAX_ACT4_OUT="$RUN_ROOT/act4-build"
nice -n 10 rvw --project examples/naxriscv regress plan \
  --act4 examples/naxriscv/rvw/act4-rv64/profile.json --json
nice -n 10 rvw regress act4-build \
  --profile examples/naxriscv/rvw/act4-rv64/profile.json \
  --checkout "$ACT4_CHECKOUT" --out "$NAX_ACT4_OUT"
nice -n 10 rvw --project examples/naxriscv regress run --suite act4-rv64 \
  --config rv64ima --source "$NAXRISCV" --rvfi-trace --jobs 4 \
  --no-index --out "$RUN_ROOT/act4-rv64ima"
nice -n 10 rvw regress cosim "$RUN_ROOT/act4-rv64ima" \
  --platform examples/naxriscv/rvw/platform-rv64ima.json
```

Repeat the run and comparison with `rv64imasu` and
`platform-rv64imasu.json`. The macOS Sail and Z3 setup is in
[ACT4](../../../../docs/ACT4.md). Keep generated files outside Git.
