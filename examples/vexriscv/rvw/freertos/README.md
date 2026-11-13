# FreeRTOS on VexRiscv RTL

This is a two-task workload for FreeRTOS Kernel V11.2.0. The build script
requires clean kernel revision `0adc196d4bd52a2d91102b525b0aafc1e14a2386`.
Keep that external checkout outside the workstation repository.

```sh
git clone --branch V11.2.0 --depth 1 https://github.com/FreeRTOS/FreeRTOS-Kernel.git /path/to/kernel
python rvw/freertos/build.py --kernel /path/to/kernel --out rvw/out/freertos.elf
rvw/run.sh run --elf rvw/out/freertos.elf --out rvw/out/freertos \
  --soc-map live-devices.json --max-cycles 500000 --seed 1 --mem-latency 0 --rvfi-trace
```

Run these commands from the example project directory. The RTOS creates two
tasks. Each task writes three UART lines and delays for timer ticks. The
payload requires at least six ticks before it reports success through tohost.
The generic CLINT model supplies the real timer interrupt pin. No scheduled
interrupt override or QEMU execution is used.

For a resumable run, use the project checkpoint harness:

```sh
RVW_BOOT_MAX_CYCLES=500000 rvw/checkpoint-probe.sh rvw/out/freertos.elf \
  rvw/out/boot-save rvw/out/boot.json save 5000 - live-devices.json
RVW_BOOT_MAX_CYCLES=500000 rvw/checkpoint-probe.sh rvw/out/freertos.elf \
  rvw/out/boot-resume rvw/out/boot.json restore 5000 - live-devices.json
```

The saved state contains live RTL registers and memories, bus responses, RAM,
cycle and retirement counts, C2 prefix, UART, CLINT and PLIC state. Restore
starts a new native model and restores that state before further execution.
The snapshot is trusted same-build state. It is not a portable simulator image.
Both commands continue to program completion. `devices.json` holds UART output.
Set `RVW_VEX_LOCK=vex-simsrv` and use a private `VEXRISCV` checkout for these runs.

`FREERTOS_KERNEL=/path/to/kernel` enables `rvw/tests/test_freertos.py`. The test
builds the real kernel and requires complete C2 and UART equality after restore.
The example is M-mode only. It has no MMU or supervisor mode. Linux and OpenSBI
boot on this configuration are not supported. No VexiiRiscv Linux run is claimed.

Native validation on 2026-11-13 used private VexRiscv revision
`a62c145aa042a5de874344e0a7683bd7c8c8c870` and Verilator. The standard bus
harness completed at 28,881 cycles with 8,667 retirements. The manual-clock
checkpoint harness uses a different bus timing policy. It completed at 9,421
cycles with 6,480 retirements. These are separate runs, not a speed comparison.

The bridge checkpoint was taken at cycle 7,206 and retirement 5,000. A new
process restored it and produced the exact full C2 SHA-256 and UART output of
the uninterrupted bridge run. See [the sample](results.json). No Linux boot
attempt was made. Both shipped example configurations lack the required
supervisor/MMU setup. A Linux-capable VexiiRiscv configuration remains open.
