# AHB-Lite agents

This profile follows [Arm IHI 0033A](https://documentation-service.arm.com/static/5f914801f86e16515cdc2a27).
It uses one manager, a single layer, 32-bit address/data and little-endian
byte lanes. It supports SINGLE, INCR, WRAP4/8/16 and INCR4/8/16 bursts.
It supports byte, halfword and word transfers. HREADY is the selected
subordinate's HREADYOUT. Arbitration, SPLIT, RETRY, AHB5 extensions and
multi-layer switching are outside this AHB-Lite profile.

## UVM

Compile `ahb_if.sv` before `ahb_pkg.sv` with the pinned UVM package from
[the UVM guide](../../README.md). Define `UVM_NO_DPI`. Enable timing,
assertions and coverage. Set config DB key `bus` as `virtual ahb_if`.
Instantiate `ahb_checker`. Connect `agent.m.ap` to a project scoreboard.
The default active agent supplies a manager driver and sequencer.
Set config DB bit `subordinate_role` to use its reactive RAM instead.
Set `is_active` to `UVM_PASSIVE` for a monitor only.

`directed` visits all burst encodings and transfer sizes. It writes then
reads each burst and sends two invalid-address accesses. `random_sequence`
randomizes legal bursts and data. `error_sequence` sends a four-beat write.
Set driver `inject_address` to mutate address during a wait in that sequence.
The `+bad_manager` fixture option guarantees that wait. `+buggy` corrupts
read data in every lane. The normal fixture has seeded waits and two-cycle
error responses. Its 256 bytes reset to zero. Error writes have no effects.
These register policies belong to the fixture, not to AHB.

The passive monitor reconstructs address/data phases independently. It
checks burst order, length, control and the 1 KB boundary. Interface
assertions check alignment, stalled controls/data and two-cycle errors.
The scoreboard compares only active read byte lanes and updates only
active write lanes. It covers direction, errors, waits, burst and size.
Call `reset_model()` when your DUT resets.

Run the supplied native UVM campaign with:

```sh
nice -n 10 rvw/.venv/bin/python Uvm/vip/ahb/smoke.py --out /tmp/ahb-new
```

The script enforces the Accellera archive pin. It has a 120-second build
limit and checks specific failure diagnostics for three seeds. UVM runtime
and reactive subordinate qualification remain open. The sources passed
Verilator lint against the pinned UVM package. Lint is not a runtime pass.

## Python and cocotb

`rvw.vip.ahb` provides `Manager.burst`, `Subordinate.step`, `Monitor.sample`,
`RegisterScoreboard`, `sequences`, `random_sequences` and `inject`.
`Manager` drives the next address while the prior transfer supplies data.
It holds both phases across waits. Pass a clock callback that returns the
pre-update sample. The monitor callback receives each completed beat and
reset abort. Send a reset sample and reset your scoreboard when reset occurs.

`CocotbAgent` has async `burst`, `run_monitor` and `run_subordinate` methods.
Use lower-case `Pins` field names and `clk` as DUT ports. Start the monitor
once. Drive reset externally. The manager drives on falling edges and
samples on rising edges before sequential updates. The reactive model
waits 1 ps after falling edges before it reads manager controls. Use a clock
period greater than 2 ps. Importing the cycle library does not need cocotb.

Install `cocotb==2.0.1` in the rvw environment. Run the small RTL campaign:

```sh
nice -n 10 rvw/.venv/bin/python Uvm/vip/ahb/cocotb_smoke.py --out /tmp/ahb-cocotb-new
```

The campaign uses three seeds. Each runs directed and random bursts against
good RTL and a read-corrupt RTL variant. Corruption must produce `AHB_DATA`.
The Python tests also check illegal phases, waits, errors and reset aborts.

## Decisions and limits

The scoreboard uses an independent byte memory. It never predicts read
values from responses. The checker has no artificial wait limit; the driver
has a 1000-cycle test timeout. The passive checker permits BUSY phases but
the sequence library does not insert them. Locked traffic is not qualified.
Four-state X checks and reactive subordinate pin integration need separate
qualification. Component tests do not establish SoC conformance.

## Bounded Python RTL evidence

The Python cocotb adapter passed a seeded good RTL test and detected the
controlled bad RTL result. See `Uvm/vip/rtl/README.md` for commands and
fixture scope. This does not establish full protocol conformance or UVM
runtime qualification.
