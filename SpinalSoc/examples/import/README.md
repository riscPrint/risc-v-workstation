# Import an OpenCores UART

The example uses the open [OpenCores UART source](https://github.com/freecores/uart16550/tree/2b0ad80d0968f201f95506854ad769c8a44abe2b).
Pin revision `2b0ad80d0968f201f95506854ad769c8a44abe2b` in a private checkout
outside this repository. The example does not download or change it.

`uart.toml` declares the module, source list, Wishbone roles, serial/modem
ports and two ordinary registers. It selects the source's 8-bit bus profile.
The composer presents word-spaced registers on its 32-bit APB fabric.
The descriptor has a 32-byte window and address shift 2. The map describes
only scratch and line-control registers. It does not claim a complete UART
register model. Software still uses the other UART register offsets directly.

```sh
rvw soc import-ip SpinalSoc/examples/import/uart.toml --root "$UART_ROOT/rtl/verilog" --base 0x10000000 --out SpinalSoc/out/uart-import
# Build a composed independent-master test with private VexRiscv build inputs.
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/python SpinalSoc/examples/import/build.py --root "$UART_ROOT/rtl/verilog" --out SpinalSoc/out/import-uart
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/rvw regress cocotb SpinalSoc/out/import-uart/bench.json --out SpinalSoc/out/import-uart-run --seed 31 --json
```

The first command writes `import.json`, captured `bundle.v`, `bridge.v` and a
Scala wrapper. Add the region and binder from `import.json` to a composition.
Build that wrapper with the generated top. Source hashes include headers.
The generated files stay local. The source license headers remain in the
capture. Keep the upstream license terms when redistributing the capture.

The directed bench drives the generated SoC through VerificationCore. It
checks scratch writes/reads, divisor alias, serial transmit frames through the
UART VIP, and an independently driven receive frame. This is a component test.
It executes no CPU. Icarus preserves the upstream RTL's `#1` delays. The
standard Verilator C3 worker refuses these delays without a timing option.
No source delay is removed. IP-XACT bus import, source-port inference,
Wishbone pipelining/retry, vendor IP and full UART compliance remain outside
this descriptor profile. Generation alone is not a simulation pass.

On 2026-11-13, the wrapper compiled and elaborated with SpinalHDL 1.15.0.
Icarus passed the composed directed test at seed 31 with zero skips. It
completed 23 checks, two transmitted frames and one received frame. The UART
agent checked transmit bytes independently. No CPU, full register audit,
interrupt campaign, C1 acceptance or hardware run was performed.
