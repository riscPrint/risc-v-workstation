# FP coverage and directed operands

| Bin dimension | Current scope |
|---|---|
| Instructions | Add, sub, mul, div and sqrt, S or D |
| Rounding | RNE, RTZ, RDN, RUP and RMM; dynamic RM uses preceding fcsr |
| Operand classes | Signed zero, subnormal, normal, infinity, quiet NaN, signalling NaN |
| Flags | All 32 masks; sticky prior flags make raised flags unknown |
| Source cross | Each source separately; no operand tuple cross |
| Unsupported | FMA, conversions, comparisons and moves |
| RTL closure | NOT RUN; no closure claim |

The generator draws every pair of six representative classes. It adds seeded
random raw-bit pairs. It clears fcsr before each arithmetic instruction.
Spike supplies expected arithmetic results through strict cosim. Tohost
checks termination. Arithmetic has no independently hard-coded oracle.

```sh
rvw/.venv/bin/python examples/vexiiriscv/rvw/fpu/programs.py \
  --width 64 --seed 1 --out "$RVW_FPU_RUN_ROOT/directed64"
```

Compile `classes.S` with `-march=rv64imafdc_zicsr_zifencei -mabi=lp64d
-nostdlib -nostartfiles -T examples/vexiiriscv/rvw/fpu/act4-64/link.ld`.
Use `rvw64fp.toml`, suite `fp-directed`, and strict `rvw regress cosim`.
Use RV32IMAFC, ILP32F and the 32-bit linker path for width 32.

```sh
rvw/.venv/bin/python examples/vexiiriscv/rvw/fpu/coverage.py \
  --width 64 --out "$RVW_FPU_RUN_ROOT/coverage64.json" TRACE...
```

Use only validated C2/2 state traces. Each input trace has a fresh register
history. Unknown operands and accrued flags give no hits. The report keeps
all flag combinations as holes, including combinations that need later
reachability review. It does not call a reference-only trace DUT coverage.
No unreachable-bin waiver or whole-FPU coverage claim is implicit.
