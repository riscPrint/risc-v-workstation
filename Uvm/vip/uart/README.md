# UART agents

The agents support 5 to 9 data bits, no/even/odd parity, one or two stop
bits, and an integer baud period of at least four sample-clock cycles.
Frames use a low start bit, LSB-first data and high idle/stop bits.
The monitor samples at bit centres. It reports parity and framing errors
as frame fields. After a bad stop bit, it waits for high idle before it
can detect the next start bit. Unknown Python line values raise an error.

`uart_if.sv` defines TX, RX and the framing configuration. `uart_pkg.sv`
contains drivers for both wires, passive monitors, an echo subordinate,
directed/random/error sequences, coverage and a byte-stream scoreboard.
The interface names are from the manager view. Set `subordinate_role` to
make an agent receive TX and echo on RX. The manager drives TX and observes
RX. Connect `agent.m.ap` to a project scoreboard.

`fixture.sv` is a seeded behavioral serial echo DUT. It has no UART register
or hardware FIFO. `+buggy` changes received byte data. `+errors` in the test
top transmits a bad stop and parity bit. The test expects those error
observations. Set the framing fields before reset is released.
`smoke.py` uses the pinned Accellera UVM build flow and three seeds.

The Python module is `rvw.vip.uart`. `Config` declares framing and bit
period. `Driver` sends a frame through a sample callback. Both UART roles
use the same driver. `Monitor` decodes immutable `Frame` values.
`Loopback` delays complete frames with a seeded schedule. `Scoreboard`
checks byte order and error fields. `Fifo` supplies a separate software
reference with a declared depth, IRQ threshold, sticky error/overrun bits,
and drop-newest overflow policy. Call `receive` for each reference frame.
Call `check_read` for each software read. Call `check_status` with observed
FIFO level, IRQ, overrun and error state. Use another policy when the DUT
has different register semantics. `sequences` and `inject` supply repeatable
traffic and byte/parity/stop faults.

`CocotbAgent` uses DUT-view `tx` and `rx` names, plus `clk` and `reset_n`.
It sends on DUT RX and observes DUT TX. The async echo subordinate is
optional. Cocotb imports occur only when an async method runs.

## Checks

```sh
rvw/.venv/bin/python -m pytest rvw/tests/test_vip_uart.py -q
verilator --lint-only --timing --assert -Wno-fatal +define+UVM_NO_DPI \
  +incdir+PATH_TO_UVM/src PATH_TO_UVM/src/uvm_pkg.sv \
  Uvm/vip/uart/uart_if.sv Uvm/vip/uart/uart_pkg.sv \
  Uvm/vip/uart/fixture.sv Uvm/vip/uart/test.sv --top-module top
```

## Decisions and limits

This is digital serial verification at a declared sample clock. It does
not model analog thresholds, metastability, baud drift, flow-control pins,
or fractional stop-bit periods. It does not infer a DUT register map.
The SV bus uses two-state pins. Python refuses unknown line samples.
FIFO and IRQ tests check the reference policy and its observed-state hooks.
They do not qualify a hardware UART FIFO or interrupt path.
Mid-frame reset aborts the monitor state. Projects must reset scoreboards
and cancel in-flight cocotb sends with the DUT.

UVM runtime builds and cocotb RTL runs were not run. Native serial timing,
FIFO boundaries and IRQ behavior remain open under issue #202 until a
project binds and runs the register/FIFO observations against its DUT.
