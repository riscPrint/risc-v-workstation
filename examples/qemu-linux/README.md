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
