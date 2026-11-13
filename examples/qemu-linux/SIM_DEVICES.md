# Simulation device and Linux recipe

The standard library plugin is `RiscvSim/src/main/cpp/PythonDevices.cpp`.
See [the ABI and build requirements](../../RiscvSim/src/main/cpp/DEVICES.md).
Each handle receives project JSON. For example:

```json
{"model":"ns16550"}
```

Timer and PLIC layouts use the existing `devices.json` data. Subtract the
mapped device base from every register address before passing a layout to a
plugin handle. Set `cycles_per_tick` explicitly. These models do not select
core input signals. The core adapter must route the output bits and dispatch
bus requests to the selected handle. The current VexRiscv adapter has no such
bus dispatch. The QEMU boot below uses QEMU devices, not the plugin library.

## Linux reference boot

Use the exact images pinned in `prebuilt.json`. Fetch both URLs from that
file into a directory outside the repository. The script verifies their
SHA-256 values before use. Supply QEMU's OpenSBI `fw_dynamic` binary.
Install `dtc` and `qemu-system-riscv64` first.

```sh
nice -n 10 rvw/.venv/bin/python examples/qemu-linux/sim-soc-boot.py \
  --images /path/to/pinned-images \
  --firmware /path/to/opensbi-riscv64-generic-fw_dynamic.bin \
  --out /path/to/new-boot-directory
```

`sim-soc.json` is an `rvw.soc/1` map. The script calls the same generator as
`rvw soc generate`. It keeps the generated RAM node and adds explicit project
bindings for a CPU, UART, CLINT, PLIC and power-off register. Device register
ranges come from the map. Node paths are fixed in this project recipe.
A moved device is refused until its project binding is updated. The PLIC
map reserves a power-of-two decoder window. Only the declared registers are
used. The script compiles `soc.dts` with `dtc` and gives `soc.dtb` to QEMU.
It selects the existing minimal BusyBox initramfs from the pinned installer.
No installer runs. No source build or package install occurs in this recipe.

On 2026-11-13, QEMU 11.1.3 and its OpenSBI firmware booted the pinned Debian
kernel to `RVW_LINUX_USERSPACE_OK` and powered off with exit code 0.
The generated DTB SHA-256 was
`86fd47229d3f929140ab1251c58997483e38efc77d0b7d144c99301acc34dbe0`.
The image SHA-256 was
`08f6dbe2dd3b1b411e26b65c27b89f780e8af5d3d0ef4cde84a9f3291e2440f2`.
`boot.json` records all input digests, command, timeout state and return code.
A pass requires the userspace marker, exit code 0 and no timeout.

The same image needs an RV64 core with the kernel's ISA extensions,
S-mode, Sv39 page tables, page faults, fences, timer interrupts and external
interrupt delivery. The platform needs sufficient RAM, matching UART and
interrupt-controller addresses, an SBI implementation and the generated DTB.
The reset path must set a0 to the hart ID and a1 to the DTB address.
A real adapter must load the same firmware, kernel, initramfs and DTB bytes.
It must reserve their memory and connect the bus devices and interrupts.
The bundled RV32IM, M-only VexRiscv example cannot boot this RV64 kernel.
No RTL Linux boot, plugin-backed Linux boot or timing equivalence is claimed.

The reference boot follows the [QEMU virt boot interface](https://www.qemu.org/docs/master/system/riscv/virt.html).

`sim-plugin-options.json` supplies separate handle configurations for all five
device kinds. Its timer and PLIC offsets come from this project's device map.
Select one object as the plugin's `projectJson`. The example timer ratio is
10 cycles per tick. It is configuration data, not a measured RTL clock ratio.
The sample PLIC stimulus asserts UART source 10 at cycle 1. It does not wire
a live UART handle to a PLIC handle. A core adapter must supply that wiring.
