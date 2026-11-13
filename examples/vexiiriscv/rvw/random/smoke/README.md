# Measured smoke suite

The exact set-cover search uses the four native characterization workloads.
Its minimum set has 4 tests. This minimum applies only to
these measured point sets. It does not prove the best suite for other inputs.

The budgeted selector chooses 3 tests with a 180-second adapter
deadline and a declared 120-second startup allowance. The suite completed
in 150.6 seconds. All selected C1 runs passed. The deadline
covers the lock wait, adapter startup, build and program execution. Cleanup
can take additional time after a timeout.

The selected historical signatures cover 27644 of 27645 observed
points. The full native denominator is 32703. Unhit native points
stay outside the observed signature target. These C1 smoke runs do not earn
new coverage or strict reference credit.

See [the result](result.json) for test names, costs, model hashes and input
hashes. Raw C1 and adapter output remain under `rvw/out/dv/smoke-vexii`.
Run `rvw cov smoke --database code.json --budget-s 180 --startup-s 120
--json` to plan. Add `--run --project PROJECT --work-dir NEW_DIRECTORY`
to enforce the adapter deadline. Use the private core and lock settings
from the native sample.
