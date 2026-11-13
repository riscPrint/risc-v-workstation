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
