# I2C agents

This digital profile sends and observes eight-bit words with a ninth ACK
bit. The Python manager supports reads, writes, STOP and repeated START.
Both managers check arbitration on transmitted one bits. Clock stretching
has a bounded wait. Arbitration loss releases both enables.

The SV package follows the existing VIP layout: item, directed and random
sequences, manager driver, passive monitor, coverage, scoreboard and agent.
The monitor emits data and ACK. Connect its analysis port to a project
scoreboard. The fixture ACKs each byte. `+buggy` returns NACK instead.
The fixture is not an addressed register device. SV reads and a reactive
UVM subordinate remain open. Python's cocotb adapter sends addressed writes.

## Open-drain contract

Only low-enable outputs are allowed. A one means pull low. A zero means
release. The interface resolves each line as the inverse OR of all low
enables. This models pull-ups on two-state backends. It does not model
analog rise time. Never connect push-pull high drivers to this interface.
Four-state backends must reject X/Z samples after line resolution. Python
raises `I2C_UNKNOWN_LINE`. Cocotb requires the caller to declare resolved
open-drain RTL wiring. It refuses the default undeclared backend.

The passive monitors permit one provisional bit before a START or STOP.
This is the SCL rising edge used to establish that boundary. Two or more
partial bits cause an error. A monitor cannot prove analog timing limits.
Ten-bit addresses, high-speed mode and bus recovery are outside this profile.

## Checks

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_i2c.py -q`.
Lint the four SV files with the pinned UVM package and Verilator.
UVM runtime builds and cocotb RTL runs were not run for this change.
Issue #205 remains open for reactive roles and runtime qualification.

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
