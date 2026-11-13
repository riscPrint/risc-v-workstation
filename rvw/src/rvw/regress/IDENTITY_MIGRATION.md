# Generic input identity migration

Issue #76 is not safe to complete from the current evidence.

| Shipped regression configuration | Adapter | Identity status |
| --- | --- | --- |
| `rvw/configs/boom.toml` | `RiscvSim/boom/run.sh` | Enables identity and identity_capture. Still declares generic command and selected toolchain inputs. |
| `examples/boom/rvw.toml` | `RiscvSim/boom/run.sh` | Same adapter and capture contract. |
| `examples/vexriscv/rvw.toml` | `examples/vexriscv/rvw/run.sh` | Enables identity and identity_capture. Still declares generic command and selected toolchain inputs. |

These are the three shipped C1 regression configurations found under
`rvw/configs` and `examples`. `examples/security/adapter.py` is a separate
security experiment protocol, not a configured C1 regression adapter.
Third-party adapters and test fixtures are not a closed external inventory.

The BOOM and VexRiscv launchers call `RiscvSim/scripts/native-identity.py`.
Its native tool collector records Verilator, selected compilers/linkers, make,
ar, sh, bash, perl and java. It does not replace the complete generic command
list. For example, the shipped configurations still capture cat and dirname
through `Inputs._initialize` in `rvw/regress/captured.py`. The collector's
cache_enabled flag does not establish capture of those command bytes.

The selected compiler and environment checks in `Inputs.verilator_toolchain`
also remain fail-closed prerequisites before execution. The existing tests in
`test_regress_round23_toolchain.py` retain missing/opaque compiler rejection.
`test_regress_identity_migration.py` proves that changing a declared command
invalidates reuse even when an adapter supplies its identity. This is local fake
adapter evidence, not a native BOOM or VexRiscv completeness result.

Before removing input_commands, input_commands_by_platform and
input_verilator_toolchain, the simulation adapter owner must replace their
captured dependencies and negative tests with adapter-owned complete identities.
Then regression management can reject or migrate the old configuration fields
and remove their capture code together. Do not simply delete declarations or
weaken missing-input rejection. No simulation-engine file was changed for this
audit. Native completeness and RTL tests have NOT RUN.
