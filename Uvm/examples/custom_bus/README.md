# Native custom-bus project adapter

This example exercises `rvw uvm new --adapter` on real RTL. The project
uses custom pin names and declares APB4 semantics. The adapter maps each
pin to the existing APB Python agent. No bus type is inferred from names.
The declared database fixture selects `example.CustomLink`. It does not
claim Scala extraction or automatic discovery of a new protocol.

Run from the repository root with Verilator, cocotb and pyuvm installed:

```sh
nice -n 10 rvw/.venv/bin/python Uvm/examples/custom_bus/run.py --out /tmp/custom-bus-new
RVW_UVM_CUSTOM_NATIVE=1 nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/test_uvm_custom_bus.py rvw/tests/test_uvm_custom_bus_native.py -q
```

Use a new output directory. The runner creates the database and invokes the
existing generator with `adapter.json`. The generated bench copies the
project scenario. The scenario binds the custom pins, resets the RTL, and
uses the existing APB manager and register scoreboard. Each transfer has
two wait cycles. Traffic covers four words, byte masks, error addresses,
reads and writes. The good run requires 82 compared transfers and 83
positive scenario checks at seed 17. It records `custom-checks.json`.

The second run corrupts RTL read data. It must fail with `APB_DATA` and
must not write the completion counts. Missing or skipped tests cannot
satisfy either control. The runner records source hashes and tool versions
in `qualification.json`. C3 logs remain in the good and bad run directories.

## Measured result on 2026-11-13

See [the recorded result](native-2026-11-13.json). The good test passed.
The corrupt read failed with the required diagnostic. These are component
checks of the project adapter and explicit APB4 binding. No CPU, C4,
new protocol, asynchronous clock or full APB qualification follows.
