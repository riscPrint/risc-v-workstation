# Minimal Linux workload

The kernel source is Linux v6.6.60 at commit
`9b5aad3a7498c261116a0251fe57f14ba9c4c6cf`. Keep the source and output outside
the repository. `build.sh SOURCE OUT` checks the source revision. It builds
an RV64IMAC static init and a newc archive. The archive contains `/init` and
`/dev/console`. Init writes `RVW_LINUX_USERSPACE` and calls the reboot syscall
with `LINUX_REBOOT_CMD_POWER_OFF`.

Set `RVW_LLVM_BIN` and `RVW_LLD_BIN` to the compiler and linker directories.
Put RISC-V GCC, GNU make, Flex and Bison on PATH. On macOS, set
`RVW_HOST_ELF_HEADER` to a host-compatible ELF header. The RISC-V toolchain's
musl-derived `include/elf.h` is suitable. The recipe copies that header into
the output directory. It also supplies a host-only UUID name adapter for
`file2alias.o`. It does not change the pinned kernel source.

The kernel starts with `allnoconfig` and uses the tiny allocator settings. The recipe enables RV64, Sv39, SBI,
compressed instructions, ELF loading, initramfs, the timer and the 8250 console.
It disables SMP, floating point, modules, networking and block storage.
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
