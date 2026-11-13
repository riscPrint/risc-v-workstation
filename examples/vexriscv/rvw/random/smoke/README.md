# Measured smoke suite

The exact set-cover search uses the four native characterization workloads.
Its minimum set has 2 tests. This minimum applies only to
these measured point sets. It does not prove the best suite for other inputs.

The budgeted selector chooses 2 tests with a 180-second adapter
deadline and a declared 120-second startup allowance. The suite completed
in 88.3 seconds. All selected C1 runs passed. The deadline
covers the lock wait, adapter startup, build and program execution. Cleanup
can take additional time after a timeout.

The selected historical signatures cover 17915 of 17915 observed
points. The full native denominator is 21429. Unhit native points
stay outside the observed signature target. These C1 smoke runs do not earn
new coverage or strict reference credit.

See [the result](result.json) for test names, costs, model hashes and input
hashes. Raw C1 and adapter output remain under `rvw/out/dv/smoke-vex`.
Run `rvw cov smoke --database code.json --budget-s 180 --startup-s 120
--json` to plan. Add `--run --project PROJECT --work-dir NEW_DIRECTORY`
to enforce the adapter deadline. Use the private core and lock settings
from the native sample.
