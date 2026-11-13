# DRAM model integration contract

`rvw.vip.dram-model/1` declares a model name, version, functional/timing
mode and positive clock period in picoseconds. Python `Adapter` requires
an explicit backend callback. It sends each command and the contract.
The callback must return read data. Timing mode also requires the response
cycle. Missing backends and missing read evidence are errors.

The independent Python checker supports ACT, PRE, RD, WR and all-bank REF.
It checks open rows, tRCD, tRP, tRAS, tRFC and read latency in declared
cycles. Data is one 64-bit word per row/column location. Full writes are
supported. The caller selects timing values. Reset clears model state.
These checks are a reduced command profile, not a complete JEDEC checker.

SV provides a UVM contract object, command item, abstract native model
class and adapter integration point. A project implements `execute` and
response scheduling with its chosen backend. The stub fixture never
accepts a command. It cannot produce a pass. The adapter does not silently
replace an absent native model with a behavioral approximation.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_dram.py -q`.
The Python tests use explicit mock callbacks. They qualify the contract,
not a native DRAM model. SV lint checks integration syntax only. No native
DRAM model, controller campaign or UVM runtime build was run. Board signal
integrity, calibration, electrical compliance and memory signoff are absent.
