# Cacheless SMP example

This example runs two to eight RV64IMA VexiiRiscv RTL cores in Verilator.
Each core has a separate fetch bus, LSU bus, reset PC and retirement probe.
All cores use one simulation RAM. The simulation memory service implements
LR/SC reservations and the nine standard AMOs at word and doubleword widths.
It invalidates overlapping reservations when a write is accepted.

## Setup

Use a private external VexiiRiscv checkout. No core source is changed.
The pinned revision is `9f70315deb3390b283995c5b8f1bd38215ecf52b`.
Its SpinalHDL pin is `de72faf6062206a89b445e5cc07e32ed982712c8`.
Its rvls pin is `847ce99fd2b28a5c0ccb1ec2683311cf97a9fefc`.
Use JDK 21, sbt, Verilator and RISC-V GCC.

```sh
export RVW_HOME=/path/to/risc-v-workstation
export VEXIIRISCV=/path/to/private/VexiiRiscv
export RVW_VEX_LOCK=vex-mem
# For a new checkout only:
examples/smp/rvw/bootstrap.sh
source /path/to/spinal-boom/env.sh
export PATH=/opt/homebrew/opt/riscv-gnu-toolchain/bin:$PATH
rvw/.venv/bin/python examples/smp/rvw/programs.py --suite smoke --out examples/smp/rvw/out/smoke
examples/smp/rvw/run.sh run --config smp2 \
  --elf examples/smp/rvw/out/smoke/hart-0.elf \
  --hart-images examples/smp/rvw/out/smoke/hart-images.json \
  --out examples/smp/rvw/out/smoke-run --rvfi-trace --seed 17 --json
```

The launcher takes the private `vex-mem` lock. Compilation takes the `sbt`
lock. Outputs stay in this example or the private source directory.
Select `smp3` through `smp8` and build the same number of hart images for N harts.
Each entry must equal `0x80000000 + hart * 0x20000`.
RAM spans `0x80000000` through `0x81ffffff`.
Every hart must retire a nonzero store to its own ELF `tohost` symbol.
An incomplete hart prevents a passing C1 result.

## Trace and reference scope

The upstream retirement probe produces per-hart C2/2 streams in one file.
Capture order is not a memory-order oracle. The header declares physical
addresses. It declares memory dependencies unavailable until a complete
binding exists. The independent axiomatic checker must return inconclusive
for that trace. Completion alone does not establish RVWMO correctness.

Use `programs.py --suite amo` for 72 checks per hart. Each check verifies
the returned old value and the new memory value. The matrix covers nine AMOs,
two widths and four aq/rl combinations. Use `--suite lrsc` for successful
LR/SC retries and SC-without-LR failure at both widths. These programs use
separate target words per hart. They do not check cross-hart reservations.

## Decisions and limits

SpinalSoc currently exposes a single-core APB wrapper. This example uses a
small project-owned Spinal top instead. Core buses are separate RTL ports.
Shared RAM and atomic service are simulation models, not synthesized fabric.
There are no caches and no TileLink-C channels. Cache and coherence observer
bindings are therefore absent. This example cannot qualify coherent caches.
CLINT and a seven-source machine-context PLIC are simulation models.
CPU-level MMIO, HSM, IPI, PLIC and FENCE.I campaigns are NOT RUN. Do not use this example as a Linux-capable SoC.
The identity is available, but complete reusable build-input capture is not
claimed. `input_complete` remains false.

## Measured results

On 2026-11-13, the three-hart smoke passed in Verilator at seed 17.
It took 86 cycles and retired 35 instructions: 11, 12 and 12 per hart.
All three C2/2 completion records report pass. The C1 instruction count equals
the validated C2 retirement count. This is simulation evidence, not hardware
qualification. Five Python tests passed. The native source build passed.
See `rvw/smoke-result.json` for the core, RTL and trace hashes.
