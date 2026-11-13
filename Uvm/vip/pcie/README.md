# Optional PCIe transaction-model adapter

A project supplies a native model name, version and explicit bridge.
No model is downloaded or substituted. Python checks enumeration identity,
command-register enables, aligned address windows, posted write effects,
read completion tags/data and declared DMA effects in host memory.
The independent byte reference starts at zero. The backend must expose
host memory effects for DMA checks. Configuration writes must return the
actual memory-enable and bus-master state. Missing evidence is an error.

The SV UVM adapter provides a native-model extension point and bounded
address/completion checks. Its byte reference also starts at zero.
Enumeration and DMA checks are in the Python adapter. The SV bridge
fixture is inert. It is not a native endpoint. Projects must implement
native model integration under their own specification and model access.

The semantic adapter is not a TLP codec. Split completions, MSI/MSI-X,
ordering attributes, retries, error recovery, link training and PHY
compliance are outside this profile. No electrical compliance is implied.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_pcie.py -q`.
Tests use mock model callbacks only. SV lint checks integration syntax.
Native PCIe models, endpoint RTL, UVM runtime builds and PHY tests were
not run. Issue #215 remains open for native model qualification.

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
