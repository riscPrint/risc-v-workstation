# Composed VexRiscv SoC

This example wraps the real RV32IM VexRiscv core. Instruction and data traffic
share a Spinal AXI arbiter. The composer supplies RAM, UART, CLINT, PLIC and a
finisher. The reset PC is `0x80000000`. RAM has 64 KiB. Reset is asynchronous and active high. The wrapper connects
MSIP, MTIP and MEIP. It has no cache, MMU, supervisor mode or debug unit.
`debugReset` resets the core and wrapper arbiter. The composed top ties it low.

Use a private core checkout at `baf7dc82f855eddaf5b0a20a6802c526f127e38a`.
Keep build output in this worktree. Set these variables from the repository root:

```sh
source /path/to/spinal-boom/env.sh
export RVW_HOME="$PWD"
export VEXRISCV=/path/to/private/VexRiscv
export RISCV_TESTS_SOURCE=/path/to/riscv-tests
export PATH="/opt/homebrew/opt/riscv-gnu-toolchain/bin:$PATH"
SpinalSoc/examples/vex/build-programs.sh
rvw/.venv/bin/python SpinalSoc/examples/vex/configure.py --out SpinalSoc/out/vex-project
rvw --project SpinalSoc/out/vex-project/rvw.toml regress run --suite smoke --no-index --out SpinalSoc/out/vex-smoke
rvw --project SpinalSoc/out/vex-project/rvw.toml regress run --suite isa --no-index --out SpinalSoc/out/vex-isa
```

`configure.py` resolves the external core path and adapter inputs into a local
project file. The template is not a runnable project. The launcher holds
`vex-soc`. Scala builds also hold `sbt`. Native processes use `nice -n 10`.
The adapter composes an empty RAM image, compiles the wrapper and loads each
captured ELF through the simulator memory API. BSS and unused RAM start at zero.
C1 records core and tools revisions, ELF/RTL hashes and UART output.

The smoke suite has four programs. `hello` checks serial bytes. `interrupt`
checks a CLINT timer interrupt. `external` checks PLIC claim/complete after a
source level at cycle 200. `uart_irq` checks machine interrupt cause and UART
IIR, disables THRE IRQ, sends `I`, then writes the finisher.

The ISA suite has 49 aligned RV32UI/UM tests. It observes the actual RAM word
at the ELF's `tohost` symbol. Misaligned-data tests are excluded. MMIO writes
use full words because the peripheral profiles are APB3. Byte and halfword
ISA tests use the byte-enabled RAM path. A pass does not establish full ISA,
privileged, UART 16550 or debug compliance. RVFI export, waves and variable
memory latency are refused. Gate input identities are not qualified here.

## Cached development builds

To test a precompiled classpath, pass a file containing that classpath to
`configure.py --classpath-file FILE`. Export the same value as
`RVW_SOC_CLASSPATH` before `rvw regress`. The generated project captures every
classpath entry as an input. The normal project excludes this variable and
builds from sources through sbt. Do not use an uncaptured classpath to claim
source-based acceptance.

## Evidence

On 2026-11-13, the wrapper and private core sources compiled against SpinalHDL
1.15.0. Verilator ran with assertions. `rvw regress` passed all four smoke
programs and all 49 selected ISA tests. The UART interrupt program reported
`I`, 15180 cycles and 2028 retired instructions at seed 31 in a separate run.
Validation used a captured development classpath. The normal sbt launcher,
RVFI co-simulation, formal proofs, a debug unit and hardware were NOT RUN.

## Verification runner

`verify.S` checks readable register resets and writes on UART, CLINT, PLIC
and finisher. `verify.json` runs it through `rvw soc verify` and checks the
sampled APB pins with the VIP and register oracle. See
[the measured table](VERIFICATION.md) for counts and missing consumers.
The adapter writes `apb.jsonl` beside C1 output. Its normal source build now
uses `sbt-soc`, since all build output is private to this worktree.

The extended verification profile extracts fresh databases for both the normal
SoC and `compose-multidomain.json`. The second composition puts CLINT in a
10 MHz clock domain. Build both tops before the run:

```sh
rvw/.venv/bin/python SpinalSoc/examples/vex/build-verify.py
export RVW_SOC_CLASSPATH="$(cat SpinalSoc/out/vex-cp.txt)"
rvw/.venv/bin/rvw soc verify SpinalSoc/examples/vex/soc.json \
  --manifest SpinalSoc/examples/vex/verify.json --out NEW_DIR
```

Use the private `VEXRISCV` copy and native tool environment above. The build
uses `sbt-soc`. A cold dependency build can exceed its two-minute limit. If so,
run the same build again after the dependency cache is warm. Preparation then
extracts fresh typed databases and runs the CPU. Connectivity uses captured
RTL through `rvw formal connectivity`. The report preserves failed proofs,
missing bindings, activation gaps and structural lint findings.
