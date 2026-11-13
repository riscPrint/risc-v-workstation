# Composed VexiiRiscv wrapper

`VexiiCore` implements `AxiCoreWrapper` for cacheless RV32IM VexiiRiscv. It uses
upstream fetch/LSU AXI bridges and the Spinal shared arbiter. It connects
machine software, timer and external interrupts. `debugReset` resets the core
and wrapper arbiter. Debug transport and debug module support are disabled.
The retirement counter counts the privileged plugin's commit mask.

Use the VexiiRiscv and Spinal source revisions from
[the existing VexiiRiscv example](../../../examples/vexiiriscv/README.md).
Do not use the released SpinalHDL 1.15.0 jars for this core. This separate sbt
project builds the composer against the core's pinned Spinal sources.
Third-party source checkouts stay outside this repository.

From the repository root:

```sh
export RVW_HOME="$PWD"
export VEXIIRISCV=/path/to/private/VexiiRiscv
rvw soc compose SpinalSoc/examples/vexii/compose.json --out SpinalSoc/examples/vexii/generated
cd SpinalSoc/examples/vexii
../../../scripts/with-lock.sh vex-soc ../../../scripts/with-lock.sh sbt nice -n 10 sbt '++2.13.14!' 'runMain generated.Generate'
```

`Run.scala` accepts a TSV manifest of memory image path, seed, cycle limit,
RAM tohost address in hexadecimal, and program name. Images have 16384
little-endian 32-bit words in hexadecimal. A zero tohost address selects the
MMIO finisher. Program name `external` enables the PLIC source at cycle 200.
The serial monitor decodes the default UART profile. Each row prints a
`SOC_RESULT` observation. This standalone runner is not a C1 adapter.

The example's PMA windows match its composed RAM, UART, CLINT, PLIC and finisher
windows. VexiiRiscv's default PMA does not cover this CLINT/PLIC placement.
Update the wrapper PMA windows when you change the map.

Prepare captured inputs from the repository root, then run from this directory:

```sh
rvw/.venv/bin/python SpinalSoc/examples/vexii/prepare.py --elf SpinalSoc/programs/vex/* --out SpinalSoc/out/vexii-inputs
cd SpinalSoc/examples/vexii
../../../scripts/with-lock.sh vex-soc ../../../scripts/with-lock.sh sbt nice -n 10 sbt '++2.13.14!' 'runMain examplesocvexii.Run ../../out/vexii-inputs/jobs.tsv' > ../../out/vexii.log 2>&1
../../../rvw/.venv/bin/python check-results.py ../../out/vexii-inputs/jobs.tsv ../../out/vexii.log
```

Add the aligned RV32UI/UM ELF paths to `--elf` to include ISA programs.
Exclude `rv32ui-p-ma_data`, which needs misaligned access support.

## Evidence

On 2026-11-13, the wrapper and composed SoC compiled and elaborated against
the pinned Spinal source libraries. Verilator ran with assertions. All four
smoke programs and 49 aligned ISA tests passed at seed 31. The serial checker
confirmed `hello\n` and `I`. The core and Spinal dependencies were private
copies of cached compiled outputs. They were not rebuilt for this run.
The standalone source build, C1 adapter, RVFI co-simulation, debug and hardware
were NOT RUN. These observations do not qualify the cached source build or
full ISA behavior.
