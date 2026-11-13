# Nested task local accumulator

The installed Verilator 5.049 devel, v5.048-26-g25d4827bd with local changes,
fails this case at seed 1. It removes the assignment to `changed` from the
generated C++. It then calls the fatal report without a condition.
The case passes if the two nested task calls are replaced with inline delays.

```sh
verilator --binary --timing --coverage -Wno-fatal -j 2 --top-module top \
  Uvm/tests/repro/nested-task-local.sv --Mdir "$BUILD"
"$BUILD/Vtop" +verilator+seed+1
```

The expected result is `changed=1`. The observed result is `changed=0` and a
nonzero exit. This case does not use UVM or protocol agents.

The UVM suite checks the same data variation in its transaction scoreboard.
Its `write` function has no nested task calls. The check covers random
transactions 8 through 39. The `+constant_data` negative control must fail
with `random data did not change`. All three normal seeds must pass.

The scoreboard workaround exposes a second installed-tool limit. This build
reports `COVERIGN` for the covergroup, coverpoints and cross. The unchanged
100-percent covergroup check then fails at time 925. A passing constant-data
negative control does not qualify functional coverage.
