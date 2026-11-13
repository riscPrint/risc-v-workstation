# Optional cacheless SMP peripheral host

This host uses `rvwsmp.SmpTop` from the existing `examples/smp` path. It keeps
that path unchanged. The harts retain their fetch and LSU memory ports. RAM
and atomic service remain the external simulation adapter's work.

The wrapper intercepts `0x10000000..0x1000ffff` peripheral requests. A rotating
arbiter serves one request through the composer's simple ingress. Each hart
waits for its outstanding RAM responses before it starts MMIO. The adapter
selects the correct 32-bit lane from a 64-bit LSU transfer. Wide peripheral
accesses and peripheral atomics return an error without selecting a device.
Machine IRQ levels broadcast to both harts. This example does not provide a
multi-hart CLINT or PLIC. It is not a synthesized shared-memory subsystem.

The software map describes RV64 harts with 32 physical address bits. The RAM
binder has type `host`. It preserves the shared RAM map without creating a
second RTL memory. The host adapter loads each ELF through the existing SMP
program builder. Do not pass these ELF64 images to composer preload.

## Run

Use the pinned VexiiRiscv and Spinal revisions from `examples/smp/README.md`.
Use a private classpath file whose source and dependency identity is known.
The classpath needs the core, its pinned Spinal libraries, RiscvSim and the
Scala compiler. Use its matching IDSL plugin. Run from the workstation root:

```sh
export PATH=/path/to/riscv-gcc/bin:$PATH
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/python SpinalSoc/examples/smp/build.py --out SpinalSoc/out/smp-host --classpath-file "$SMP_CLASSPATH_FILE" --idsl-plugin "$SMP_IDSL_PLUGIN"
export RVW_SMP_PROGRAMS="$PWD/SpinalSoc/out/smp-host/programs"
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/rvw regress cocotb SpinalSoc/out/smp-host/bench.json --out SpinalSoc/out/smp-host-run --seed 31 --json
```

The directed bench reuses the existing per-hart source and linker generator.
It adds private RAM word stores/loads and one GPIO write/read pair per hart.
Every hart must write pass to its own `tohost`. Completion by only one hart
fails the bench. The minimal cocotb RAM service refuses AMOs explicitly.
Use the existing SMP adapter for atomic campaigns. This host test makes no
new atomic, coherence, memory-order, C1 or hardware qualification claim.

## Measured result

On 2026-11-13, the pinned private core and Spinal class copies compiled and
elaborated the host. Verilator passed the directed two-hart test at seed 31
with assertions enabled and zero skips. Both `tohost` values were 1. The run
took 133 cycles. Hart retirements were 21 and 22. Each hart completed two RTL
MMIO accesses and three external RAM data requests. GPIO outputs were
`0x12340000` and `0x12340001`. The cached core dependencies were not rebuilt.
The existing standalone SMP C1 campaigns were NOT RUN for this change.
