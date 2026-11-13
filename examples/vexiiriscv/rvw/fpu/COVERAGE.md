# FP coverage and directed programs

| Dimension | Definition |
|---|---|
| Instructions | Scalar F/D instructions, including FMA, conversions, moves, comparisons and compressed FP memory instructions |
| Rounding | RNE, RTZ, RDN, RUP and RMM; dynamic RM uses the preceding frm |
| Unrounded instructions | Use the preceding frm as context |
| Operand classes | Zero, subnormal, normal, infinity, quiet NaN and signalling NaN, for each FP source |
| Integer source | `not_fp` for integer-to-FP instructions |
| Loads | Classify the loaded FP bits |
| Flags | All 32 masks; prior nonzero flags make raised flags unknown |
| NaN boxing | Check computational S inputs when FLEN is 64; raw moves and stores retain their bits |
| Qualification | Complete passing DUT C2/2 bound to a conclusive C1 pass; reference-only traces get no bins |

`rvw cov fp` and MCP `cov_fp` use the same calculation. The command uses the
shared RISC-V decoder and the existing C1 coverage qualifier. A bin hit records
execution. Compare each run with Spike before a correctness or closure claim.
The report never derives a flag value from an instruction's expected behavior.
Unknown operands, reserved RM values and sticky flags get no full cross hit.

| Profile and format | Class bins before | Class bins after | Full flag crosses before | Full flag crosses after | Remaining full crosses |
|---|---:|---:|---:|---:|---:|
| RV32IMAFC, S | 856 / 1,425 | 1,425 / 1,425 | 2,004 / 45,600 | 2,579 / 45,600 | 43,021 |
| RV64IMAFDC, S | 941 / 1,405 | 1,405 / 1,405 | 2,122 / 44,960 | 2,605 / 44,960 | 42,355 |
| RV64IMAFDC, D | 903 / 1,525 | 1,525 / 1,525 | 2,045 / 48,800 | 2,680 / 48,800 | 46,120 |

Before means riscv-tests plus ACT4. After adds the directed suite. All selected
runs passed C1 and matched Spike strictly. The class count projects the full
cross onto instruction, RM, source position and class. It is not an operand
tuple cross. No flag mask is waived as unreachable. Full flag-cross closure
remains open. The raw reports list every hole and the unknown counts.

`selfcheck.py` draws one representative of each class. It adds seeded random
raw bits. It covers each scalar instruction at all five rounding modes.
It first compiles an oracle program and calls `rvw cosim generate`. It then
writes result-bit and flag checks from that Spike trace and compiles the final
program. Each operation starts with clear flags. Missing cases, traps and
missing FP results stop generation. No Python floating-point model is used.

```sh
rvw/.venv/bin/python examples/vexiiriscv/rvw/fpu/selfcheck.py \
  --xlen 32 --width 32 --seed 1 --random-cases 8 \
  --platform examples/vexiiriscv/rvw/platform32fp.json \
  --linker examples/vexiiriscv/rvw/fpu/act4-32/link.ld \
  --out "$RVW_FPU_RUN_ROOT/directed32"
```

Use `--xlen 64 --width 32` and `--xlen 64 --width 64` with the 64-bit
platform and linker to write the S and D programs into `directed64`.
The native set has 30 RV32 S, 31 RV64 S and 35 RV64 D self-checking programs.
The final CLI regenerated identical assembly and load images for all 96.
GCC temporary object names can change non-loaded ELF symbol strings.
Select `fp-directed` in the matching project. Run strict `rvw regress cosim`.
The older `programs.py` arithmetic sweep remains available. Its math results
are checked by cosim. Its `lazy-fs.S` also checks the FS states itself.

The following zsh commands regenerate the full coverage report from the
published C1 test paths. Use the run names from the FP README.

```zsh
traces=(
  "$RVW_FPU_RUN_ROOT/isa32-run"/fp-isa/rv32imafc/tests/**/rvfi.jsonl
  "$RVW_FPU_RUN_ROOT/act432-run"/fp-act4/rv32imafc/tests/**/rvfi.jsonl
  "$RVW_FPU_RUN_ROOT/directed32-run"/fp-directed/rv32imafc/tests/**/rvfi.jsonl
)
rvw cov fp "${traces[@]}" --width 32 \
  --out "$RVW_FPU_RUN_ROOT/coverage32.json" --json
```

Use the RV64 run names and `rv64imafdc` to report S with width 32 and D with
width 64. Omit the directed run to regenerate the before report. Keep the
full JSON outside the repository. The compatibility script `coverage.py`
forwards to this command.
