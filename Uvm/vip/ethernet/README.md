# Optional Ethernet packet-model adapter

A project supplies a model name, version and packet bridge. Python checks
MAC client payload bytes, descriptor ownership, buffer bounds, DMA effects,
completion lengths and interrupts. Successful receive returns descriptor
ownership to software. Declared loss/error leaves the descriptor region
unchanged, retains device ownership and raises no interrupt. Projects with
another error policy need an explicit adapter. Loss is never silently ignored.

The native bridge shares host memory with the checker. Returned metadata
alone cannot satisfy a receive DMA check. Transmit compares the model's
observed payload with the descriptor's host-memory bytes. Native backend
installation and access remain project-owned.

SV provides a packet item, abstract native-model class and packet/error/
interrupt adapter with coverage. Descriptor and DMA checks are in Python.
The byte-stream interface is a project integration point. The fixture is
inert without a model. It does not claim to be a MAC implementation.

Scope is MAC client packets of 1 to 9216 bytes. Preamble, padding, FCS,
link negotiation and PHY electrical compliance are outside this profile.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_ethernet.py -q`.
Tests use mock callbacks. SV lint checks integration syntax. Native packet
models, MAC/DMA RTL, UVM runtime builds and PHY tests were not run.
Issue #216 remains open for native model and project qualification.

## Seeded RTL endpoint result

The [semantic endpoint campaign](../rtl/CONTRACT_RESULTS.md) ran this Python
agent against good and corrupt RTL on 2026-11-13. The opt-in native suite
returned 4 passed and 0 skipped across its four profiles. Read that matrix
for the exact scope and excluded features. This does not qualify an external
native protocol model, a physical link or the SV UVM agent.

## Measured SV campaign

The [dated SV matrix](../qualification/native-2026-11-13.md) records this
fixture's compile and runtime status on Verilator 5.052. The SV model stub has no runnable UVM checks and remains unqualified.
Earlier lint/unit-only notes describe the initial test set. The dated matrix
gives the current SV result and its limits. Cocotb evidence is separate.
