# Reduced coherent event agent

This is `rvw.chi-like/1`. It is a project verification event stream.
It is not an Arm CHI wire protocol or CHI conformance claim. A project
owns its bridge to any licensed coherent interface and specification.

Events are request, snoop acknowledgement and completion. Requests are
ReadShared, ReadUnique and WriteBack. Lines are 64-byte aligned. Data is
one abstract 64-bit value per line. Each node has four request credits.
One transaction can be active on a line. ReadUnique invalidates other
holders. ReadShared downgrades a unique owner. WriteBack requires unique
ownership and updates the independent reference data. Completion restores
credit only after all required snoop acknowledgements and matching data.
Dirty forwarding, retries, ordering channels and byte enables are absent.

Python supports up to 16 nodes. SV supports four nodes and 16 lines.
Both support 16 transaction IDs. The Python directory is a trace checker.
It does not use DUT-reported ownership as its reference. The cocotb adapter
sends events through a project `PREFIX_valid/ready` bridge with fields
from `Event`. SV supplies stimulus, monitor, coverage and scoreboard.
The fixture copies events and `+buggy` changes data. Reset the scoreboard
with the DUT between campaigns; mid-transaction reset is not qualified.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_coherent.py -q`.
Lint the four SV files with pinned UVM. UVM runtime builds, coherent RTL
bridges and licensed CHI qualification were not run for this change.

## Seeded RTL endpoint result

The [semantic endpoint campaign](../rtl/CONTRACT_RESULTS.md) ran this Python
agent against good and corrupt RTL on 2026-11-13. The opt-in native suite
returned 4 passed and 0 skipped across its four profiles. Read that matrix
for the exact scope and excluded features. This does not qualify an external
native protocol model, a physical link or the SV UVM agent.

## Measured SV campaign

The [dated SV matrix](../qualification/native-2026-11-13.md) records this
fixture's compile and runtime status on Verilator 5.052. All declared normal and fault cases passed at seeds 1, 2 and 3.
Earlier lint/unit-only notes describe the initial test set. The dated matrix
gives the current SV result and its limits. Cocotb evidence is separate.
