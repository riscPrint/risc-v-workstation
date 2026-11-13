# RV64 F/D/C ACT4 profile

| Check | Result |
|---|---|
| Pinned ACT4 | `56d40ab301dba23dd3104c17bd969afbaaea1931` |
| ISA groups | F, D, Zca and Zcd; C metadata is also declared |
| F/D-only build | 200 self-checking ELFs; 84 F and 116 D |
| Final full build | 236 self-checking ELFs: F 84, D 116, Zca 32, Zcd 4; complete manifest |
| DUT run and strict Spike comparison | 236 C1 passes and 236 strict Spike matches |

This profile uses the existing reduced CSR bootstrap. It does not qualify
standard Sm bootstrap. Sail has four-state FS and the same compressed
subextensions as UDB. The final run checks the DUT and compares each retirement with Spike.
The [parent README](../README.md) records the core pin and comparison scope.

Run `rvw regress act4-build --profile
examples/vexiiriscv/rvw/fpu/act4-64/profile.json --checkout "$ACT4_CHECKOUT"
--out "$RVW_FPU_RUN_ROOT/act464"`. Use a private ACT4 checkout and the private
macOS Z3 cache from docs/ACT4.md. Select `rvw64fp.toml` and suite `fp-act4`
for `rvw regress run --rvfi-trace --jobs 2`. Run `rvw regress cosim` with
`rvw/platform64fp.json`. Use a new external output directory for each build.
