# QEMU Linux reference platform

`platform.json` declares the first Linux reference platform. It is project data,
not a BOOM address map. Run it with `rvw arch linux prepare` or `boot`.
See [the Linux flow](../../Arch/README.md#linux-reference-flow) for commands.

The device tree comes from the selected native QEMU binary. The command checks
selected properties against this file before it uses that tree. A changed QEMU
machine layout must fail these checks. Review a new platform file explicitly.
The report captures both the platform file and the emitted DTB.

## Decisions

Use one RV64 hart, 128 MiB RAM, the QEMU virt CLINT, PLIC and ns16550a UART.
Disable network input. Use only an initramfs for storage. The clock checks
refer to the model's device descriptions. They do not describe RTL timing.
No RTL device adapter is certified by these data.

## RTL adapter plan

`rtl-adapter-plan.json` defines the proposed placement, reset state and device
connections. Reuse the round-2 `rvw.cosim.devices.Timer` and `Plic` models as
reference oracles. They do not connect a DUT bus. Add an ns16550a adapter and
independent register tests before using its UART output as boot evidence.
Patch `/chosen` and the firmware reservation in the captured DTB before RTL
loading. Hash that final DTB. The unmodified QEMU dump is not a complete RTL
boot table.

The plan cannot run as a Linux adapter yet. BOOM's interrupt generator conflicts
with the PLIC base. BOOM also lacks Linux reset a0/a1 setup. The current VexRiscv
example is RV32IM. Keep model time, device-state checks, bounded instruction
comparison and RTL boot results separate.

## Bounded OpenSBI instruction smoke

`opensbi-smoke.S` and `opensbi-smoke.ld` build a reset prelude and an unchanged
raw firmware payload. The prelude sets all 31 writable GPRs to zero, then jumps
to firmware at `0x80200000` through t0. Both models execute the same prelude.
It uses 34 instructions. Compare a 162-instruction prefix to check the first
128 OpenSBI instructions. This fixture supplies no DTB and no Linux kernel.
It does not check SBI services or device state.

Build pinned OpenSBI with `rvw arch linux firmware --llvm`. Check its manifest
and firmware SHA-256 first. Set `firmware` to that build's `fw_jump.bin` path.
Then build the fixture from the workstation root:

```sh
riscv64-unknown-elf-gcc -nostdlib -static -march=rv64ima_zicsr -mabi=lp64 \
  -Wl,--build-id=none -T examples/qemu-linux/opensbi-smoke.ld \
  "-DFIRMWARE_IMAGE=\"$firmware\"" examples/qemu-linux/opensbi-smoke.S \
  -o /tmp/opensbi-smoke.elf
scripts/with-lock.sh boom nice -n 10 RiscvSim/boom/run.sh run \
  --elf /tmp/opensbi-smoke.elf --out /tmp/opensbi-smoke-run --config small \
  --seed 1 --max-cycles 4000 --wall-timeout 20 --rvfi-trace --json
```

The linker marks the firmware segment RWX because the raw image contains code
and writable data. A bounded simulation timeout is expected. It is not a boot
pass. Keep the C2 header and the first 162 instruction rows from `rvfi.jsonl`.
Do not add an end/pass row. Compare that prefix with `rvw cosim check --core
boom --elf /tmp/opensbi-smoke.elf --trace PREFIX --json`. Require 162 compared
instructions and `scope=trace prefix`. Keep `trace_complete=false` explicit.
A direct firmware entry can read unspecified reset GPR values. Do not copy
those values from the DUT into the reference to force a match.
