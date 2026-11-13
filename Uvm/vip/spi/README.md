# SPI agents

The profile has one active-low chip select and four wires: CS, SCLK, MOSI
and MISO. It supports all four CPOL/CPHA modes, 1 to 32 bits per word, and
MSB-first or LSB-first order. Chip select can cover multiple whole words.
The selected clock mode and word width must stay fixed during a selection.

`spi_pkg.sv` contains a controller driver, reactive peripheral serializer,
passive monitor, directed/random/error sequences, functional coverage and
a loopback scoreboard. `spi_if.sv` supplies the pins and idle-clock checker.
The monitor checks chip-select boundaries and word completion.
Connect `agent.m.ap` to a project scoreboard. Set `subordinate_role` to
select the peripheral. Supply response words through `agent.sub.words`.
An empty response queue returns all ones. A partial word does not consume
its queued response. The driver expected port uses the loopback policy;
projects with other peripherals must supply their own expected words.

`fixture.sv` is a digital wire-loopback DUT. The simulator seed controls
sequence data. `+buggy` inverts MISO. `+bad_manager` ends chip select in the
middle of a word. `test.sv` accepts `+cpol` and `+cpha` to select the mode.
`smoke.py` uses the pinned Accellera UVM build flow. Its default campaign
uses mode 0. Runtime mode qualification remains open.

The Python module is `rvw.vip.spi`. `Config` declares mode, width and bit
order. `Manager.transfer` drives through a callback. `Subordinate.step`
serializes queued responses. `Monitor` emits `Word(mosi, miso)` values.
`Scoreboard` compares expected full-duplex words. `sequences` supplies
seeded words. `inject` changes selection, data or clock pins.
`CocotbAgent` uses flat `PREFIX_cs_n/sclk/mosi/miso` pins, plus simulation
`clk` and `reset_n`. It supplies both roles and passive observation.
Use at least two simulation clock cycles per SCLK half-period with the
cocotb peripheral. The cocotb controller uses three cycles per waveform
state. Cocotb is optional at import time.

## Checks

```sh
rvw/.venv/bin/python -m pytest rvw/tests/test_vip_spi.py -q
verilator --lint-only --timing --assert -Wno-fatal +define+UVM_NO_DPI \
  +incdir+PATH_TO_UVM/src PATH_TO_UVM/src/uvm_pkg.sv \
  Uvm/vip/spi/spi_if.sv Uvm/vip/spi/spi_pkg.sv \
  Uvm/vip/spi/fixture.sv Uvm/vip/spi/test.sv --top-module top
```

## Decisions and limits

SPI has no generic in-band backpressure or FIFO-error indication. This
agent does not invent one. A project must connect its FIFO status and
software operations to its register scoreboard. Analog timing, shared
MISO resolution, multiple chip selects, dual/quad lanes and DDR transfers
are outside this profile. Python refuses unknown pin samples. SV uses
two-state pins. Projects must reset scoreboards with the DUT and cancel
in-flight sends during reset.

The initial test set had no runtime campaign. See the measured SV and
Python RTL results below. General DUT FIFO qualification remains open.
Issue #204 remains open for native runtime and project FIFO qualification.

## Bounded Python RTL evidence

The Python cocotb adapter passed a seeded good RTL test and detected the
controlled bad RTL result. See `Uvm/vip/rtl/README.md` for commands and
fixture scope. This does not establish full protocol conformance or UVM
runtime qualification.

## Measured SV campaign

The [dated SV matrix](../qualification/native-2026-11-13.md) records this
fixture's compile and runtime status on Verilator 5.052. All declared normal and fault cases passed at seeds 1, 2 and 3.
Earlier lint/unit-only notes describe the initial test set. The dated matrix
gives the current SV result and its limits. Cocotb evidence is separate.
