# Composed RV32 stub example

This example connects a tiny RV32 instruction stub to RAM, UART, CLINT, PLIC
and tohost through the Spinal APB3 decoder. The core source is project data.
It supports LUI, ADDI, word load/store, JAL, CSRRW and MRET only. It is not an
ISA-qualified core. Unsupported instructions stop with an error.

```sh
source /path/to/spinal-boom/env.sh
export PATH=/opt/homebrew/opt/riscv-gnu-toolchain/bin:$PATH
SpinalSoc/examples/stub/build-programs.sh
rvw --project SpinalSoc/examples/stub/rvw.toml regress run --tier quick \
  --out SpinalSoc/out/run --seed-base 17 --no-index --no-cache
```

The adapter implements C1 `build`, `identity` and `run`. Runs capture the ELF,
preload RAM, elaborate the composition and execute Verilator. The result
records RTL/input hashes, seed, cycle and retirement counts and source state.
The UART decoder samples the actual TX pin. The hello program requires
`hello` followed by a newline. The interrupt programs must reach tohost code 1.
The harness raises PLIC source 1 at measured loop cycle 200 on every run.

Outputs stay in `SpinalSoc/out`, `generated`, `simWorkspace` and `programs`.
The `soc-stub` lock protects generated sources. The `sbt` lock protects builds.
Each program rebuilds the initialized memory. No shared VexRiscv copy is used.

## Limits

The stub implements only the listed instructions and a small machine CSR
subset. Interrupt priority is reduced to the timer and external examples.
It has no RVFI, debug module, cache, MMU, byte operations or access-fault traps.
The timer test finishes in its handler. It does not test MRET behavior.
Cycle counts start after ten initialization sampling edges. They are harness
measurements, not whole-program performance measurements. Source edits mark
C1 dirty. These runs do not establish core acceptance or ISA conformance.

## Local results

On 2026-11-13 `rvw regress` ran all three programs in Verilator at seed 17.
The source tree was dirty. All three C1 results passed. No C4 acceptance or
ISA qualification is claimed.

| Program | C1 status | Measured loop cycles | Retired instructions |
|---|---|---|---|
| external | pass | 224 | 74 |
| hello | pass | 1313 | 436 |
| interrupt | pass | 111 | 37 |

Hello output from the serial pin was `hello` followed by a newline.

Set `RVW_CHECKS_ISA=1` to compile generated checks into the stub simulation.
The adapter writes `checks.json` and `checks-run.json` beside C1. A firing keeps
the C1 result at fail. Missing observations give an error. `RVW_SBT_LOCK` selects
the sbt lock; use a private name only for builds in private directories.

The 2026-11-13 hello capture generated and bound 17 checks. It completed 1,313
harness cycles and retired 436 instructions. UART output matched `hello\n`.
No check fired. One UART valid-hold check passed BMC through depth 4, in the full
SoC hierarchy, with two initial reset samples. No activation or unbounded proof
was measured. See [the counts](checks-qualification.json). This does not establish
ISA conformance or complete peripheral verification.
