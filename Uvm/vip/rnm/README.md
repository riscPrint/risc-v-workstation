# Real-number boundary stub

This is an interface contract only. No analog behavior is implemented.
Declare backend name/version, real-number handle support, channel names
and units. Python time is integer femtoseconds. Every value has separate
valid and known flags. Invalid values are not observations. Unknown or
non-finite valid values are errors. Samples must not move backward in time.
No unit conversion or implicit unknown-to-zero conversion is performed.

`BoundaryStub.evaluate` always returns `inconclusive: model_not_bound`.
The cocotb observer requires explicit real-value, known and valid handles.
SV supplies a real-number interface, UVM contract and stub observer. The
fixture's zero value has valid cleared. It is not analog evidence.
Backend support declarations are requirements, not simulator qualification.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_rnm.py -q`.
SV lint checks syntax only. No native RNM runtime, behavioral sensor/PLL
model, transistor simulation, UVM runtime build or electrical signoff was
run. Issue #217 remains open for actual native model integration.
