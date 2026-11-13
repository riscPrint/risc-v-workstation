# Debug transport on the composed VexRiscv SoC

`DmiCore` and `JtagCore` reuse `rvwvex.VexDebug.configuration` for the
`rv32im_dmi` and `rv32im_jtag` profiles from PR #896. They keep the composed
AXI wrapper, RAM, GPIO and interrupt routing. The original `VexCore()` profile
keeps its default configuration. Its optional constructor input selects a
project-owned VexRiscv configuration.

The build compiles the existing project debug plugin sources. It does not
copy a Debug Module model into the RTL. The real CPU uses the CSR plugin's
official privileged-debug interface. The DMI profile exposes DebugBus pins.
The JTAG profile exposes the upstream EmbeddedRiscvJtag TAP pins. Both expose
`debug_ndmreset` as a reset request. This example has no system reset controller.
That request needs a project binding which resets system state while retaining
the Debug Module. It is not tied back to the common reset in this profile.
System reset behavior is NOT RUN. The regular composer debugReset input stays
inactive in these directed tests.

## Run

Use the private pinned VexRiscv source and environment from the Vex example.
Run from the workstation root with RISC-V GCC on PATH:

```sh
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/python SpinalSoc/examples/debug/build.py --out SpinalSoc/out/composed-debug
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/rvw regress cocotb SpinalSoc/out/composed-debug/dmi/bench.json --out SpinalSoc/out/debug-dmi --seed 31 --json
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/rvw regress cocotb SpinalSoc/out/composed-debug/jtag/bench.json --out SpinalSoc/out/debug-jtag --seed 31 --json
```

Both benches first require CPU retirement and the expected composed GPIO
write. The DMI bench activates dmactive, requests halt, checks retirement
stops, requests resume and checks retirement restarts. The JTAG bench serves
the actual RTL pins over a local remote_bitbang socket. It invokes the public
`rvw debug tap --port PORT --out tap-results` command as a separate process.
Its report is retained beside the C3 component result. No Python DTM or Debug
Module reference model serves that socket. The socket bridge handles pin
writes, TDO reads and client quit. It is a directed test transport, not a
persistent interactive debug server.

## Measured results

SpinalHDL 1.15.0 compiled and elaborated both profiles on 2026-11-13. Verilator
ran with assertions at seed 31. Each cocotb case passed with zero skips.

| Profile | Result |
|---|---|
| rv32im_dmi | 8 accesses; halt held retirement at 23; resume increased it to 26; GPIO 0x12345678 |
| rv32im_jtag | Public TAP CLI: all 9 checks pass, zero failures or inconclusive checks |

The first DMI bench omitted the dmactive activation step and did not halt.
Adding the required activation step corrected the bench. The wrapper was not
changed for that failure. The TAP test covers the existing nine TAP/DTM checks.
It does not establish complete Debug Specification compliance. Abstract
commands, breakpoints, watchpoints, system reset, OpenOCD/GDB, C1 acceptance
and hardware debug were NOT RUN through this composed profile. Standalone
Vex debug campaigns have separate results and open defects.

The default CPU/DMA example was rebuilt after the optional configuration
change. It passed again in 2,135 cycles with 236 CPU retirements, 33 DMA
write/read pairs and finisher 1. The final JTAG run processed 5,140 pin writes.
Its retirement count includes time while the socket client waits. It is not
a performance measurement.
