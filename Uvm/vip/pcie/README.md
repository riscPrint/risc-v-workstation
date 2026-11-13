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
