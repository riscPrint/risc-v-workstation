# Minimal Linux workload

The kernel source is Linux v6.6.60 at commit
`9b5aad3a7498c261116a0251fe57f14ba9c4c6cf`. Keep the source and output outside
the repository. `build.sh SOURCE OUT` checks the source revision. It builds
an RV64IMAC static init and a newc archive. The archive contains `/init` and
`/dev/console`. Init writes `RVW_LINUX_USERSPACE` and calls the reboot syscall
with `LINUX_REBOOT_CMD_POWER_OFF`.
Init drains the tty with `TCSBRK` before it requests power-off. A tty write
can return while output is still queued. Without the drain, the QEMU control
powered off before it displayed the marker. The corrected control displayed
the marker and exited after `Power down`.

Set `RVW_LLVM_BIN` and `RVW_LLD_BIN` to the compiler and linker directories.
Put RISC-V GCC, GNU make, Flex and Bison on PATH. On macOS, set
`RVW_HOST_ELF_HEADER` to a host-compatible ELF header. The RISC-V toolchain's
musl-derived `include/elf.h` is suitable. The recipe copies that header into
the output directory. It also supplies a host-only UUID name adapter for
`file2alias.o`. It does not change the pinned kernel source.

The kernel starts with `allnoconfig` and uses the tiny allocator settings. The recipe enables RV64, Sv39, SBI,
compressed instructions, ELF loading, initramfs, the timer and the 8250 console.
It disables SMP, floating point, modules, networking and block storage.
It also disables virtual terminals, pseudo terminals, namespaces, futexes,
ELF core dumps and POSIX timer syscalls. The 8250 driver has one UART slot.
`lpj=1000` avoids delay-loop calibration. This is a simulation workload setting.
It is not a timing calibration for physical hardware.

The kernel build and userspace boot are separate checks. A built Image does
not establish a completed RTL boot. The init power-off syscall also needs an
SBI reset device and a harness shutdown binding.

The recipe uses the options from the kernel's tiny configuration with the
required OS features. GNU sed must be on PATH. Set `RVW_GNU_SED_BIN` to its
`gnubin` directory on macOS. Block storage, `/proc` and unused initrd
decompressors are disabled. The built-in archive is not compressed.

Build OpenSBI with `opensbi/build.py --linux`. Prepare the workload with
`opensbi/prepare.py --kernel IMAGE --firmware FW_JUMP --resumable --out INPUTS`.
This variant uses 32 MiB RAM and a 1 MHz simulation clock. It adds a mapped
power-off register at `0x100000`. OpenSBI writes `0x5555` there for an SBI
shutdown request. The boot-slice harness reports `shutdown` only after that
write. Check the console marker as a separate condition. Standard C1 payload
preparation keeps its previous map unless `--resumable` is selected.

Linux receives both the current `riscv,isa-base` and `riscv,isa-extensions`
properties and the legacy `riscv,isa` property. The current properties are
required when `CONFIG_RISCV_ISA_FALLBACK` is disabled.

For a stopped slice, prepare a diagnostic C1 view and make a bundle:

```sh
python rvw/linux/debug_result.py --report RUN/result.json --checkpoint CHECKPOINT \
  --elf INPUTS/reset.elf --out DEBUG_RUN
rvw bundle DEBUG_RUN --project rvw64.toml --no-rerun --no-spinaltrace --out BUNDLE
```

The converter checks the captured ELF digest and matching counters. It reports
success only when both the userspace marker and power-off request are present.
The C1 view remains inconclusive for regression acceptance because it has no
C1 replay binding. The bundle can still show available console and stop-state
evidence. No trace, wave or exact failure cause is inferred when absent.

## Long-run build profile

`boot-slices.sh` defaults to native compiler optimization level 3 and one
Verilator thread. Set `RVW_BOOT_OPT=0..3` and `RVW_BOOT_THREADS=1..64` to select
a different profile. Use these variables instead of an inherited `--threads`
flag. The launcher reaches niceness 10 once. It keeps a lower inherited
priority when it cannot raise it.

Set `RVW_BOOT_FREEZE_RUNTIME` to a new external directory for the first run.
The launcher copies the compiled classes, resources and dependency jars there.
For later runs, unset that variable and set `RVW_BOOT_CLASSPATH` to the saved
`classpath.txt`. This skips source compilation and uses the same class bytes
for restore. Input and RTL identity checks still apply. Keep the directory
until the checkpoint is no longer needed. This is same-build state, not a
portable simulator distribution.

Run the bounded profile experiment with the same starting checkpoint:

```sh
python rvw/linux/bench.py --inputs INPUTS --checkpoint CHECKPOINT \
  --classpath FROZEN_RUNTIME/classpath.txt --out BENCH --cycles 65536 --pairs 5
```

The experiment warms each profile. It alternates the order of five serial
pairs. It checks complete final RTL state, RAM, device and pending bus state
before it reports rates. It retains results and logs outside the repository.
It deletes trial checkpoints after comparison and removes its native build
directories at completion. It does not use or weaken the conclusive C1/C2
speed gate. Its rates cover bounded slices with checkpoint I/O.

The measured run used the Linux counter-enabled model at core revision
`9b63f47fe559dbba7874af9196746412fa1294c1`. Each trial restored the same
checkpoint at cycle 1,953,792 and ran 65,536 more cycles. It warmed all
profiles, then used five serial pairs in alternating order. All 18 trials
had identical complete final checkpoint state and RAM.

| Profile | Median cycles/s | Median instructions/s | Paired wall speedup |
|---|---:|---:|---:|
| Optimization 0, one thread | 1,221.28 | 512.60 | 1.0000x |
| Optimization 3, one thread | 2,286.16 | 959.56 | 1.4343x |
| Optimization 3, two threads | 310.14 | 130.17 | 0.2573x |

These rates include RTL restore and checkpoint writes. They exclude native
compilation and initial input loading. They cover one bounded Linux prefix,
without C2 or waves. They do not measure a full boot or qualify the C1 speed
gate. Earlier partial campaigns were not included. One stopped while a
separate OS run held the lock. The final campaign held the private lock for
all trials. One thread remains the default.

The Linux profile enables `zicntr`. Without it, Linux stopped at
`riscv_sched_clock` on `rdtime` with illegal-instruction cause 2. The short
`rvw/tests/test_supervisor_time.py` control enables counters, enters supervisor
mode, reads time/cycle/instret, prints `T` and requests power-off. It passed at
212 cycles and 27 retirements with no trap. This checks the configuration and
shutdown path. It does not establish a completed Linux boot.

Check the exact prepared payloads under QEMU before a long RTL run:

```sh
RVW_LINUX_INPUTS=INPUTS python -m pytest rvw/tests/test_linux_reference.py -q \
  --basetemp=EXTERNAL_REFERENCE_TEST
```

This test runs from the example directory with the native environment set.
It checks the input hashes, userspace marker and QEMU power-off exit.
QEMU completion is reference evidence. It is separate from RTL completion.
