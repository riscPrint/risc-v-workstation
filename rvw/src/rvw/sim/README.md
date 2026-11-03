# Native simulation

`backends.py` declares the guarantees of the native adapter profiles. Use
`require(backend, features)` before a run. Unknown backends and unknown or
unsupported features are errors. A profile describes this invocation, not every
feature of the simulator. It does not certify an installed version.

Verilator uses two-state values. Icarus preserves four-state X/Z values.
Neither profile guarantees pessimistic X propagation, complete SystemVerilog,
concurrent SVA or coverage. Foreign interfaces listed in the profile describe
native support. This adapter uses VPI only. Other native backends are refused
until they have a profile and conformance tests.
