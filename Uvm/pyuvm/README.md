# Python UVM base environment

Install the optional `pyuvm` extra with `uv pip install -e 'rvw[pyuvm]'`.
This extra selects pyuvm 4 and cocotb 2. pyuvm 3 requires cocotb 1 and cannot
use the current cocotb runner.

```sh
nice -n 10 rvw regress cocotb Uvm/pyuvm/bench.json --out /tmp/pyuvm-base --timeout 110 --json
```

The native fixture writes and reads a four-word RTL memory. It compares eight
transactions and checks all eight write/address bins. It uses the same ordered
expected/actual policy and bins as `Uvm/base/rvw_base_pkg.sv` in the project
UVM flow change. This is a bounded base-environment path. It is not complete
SystemVerilog/pyuvm semantic parity or CPU ISA qualification.

`rvw_env.py` supplies `BaseEnvironment`, `BaseScoreboard` and `CpuEnvironment`.
A project supplies instruction and memory agents, interrupt/debug adapters and a
strict retirement comparator through the CPU config object. Shared memory uses
little-endian bytes and explicit byte enables. The retirement monitor refuses
order gaps, duplicates and comparators that return no checked match. It does
not connect to Spike automatically. The existing native UVM Spike path remains
capture replay.

For RAL, set `register_map`, `frontdoor` and optional `backdoor` in the CPU
config. `RegisterModel` reads `rvw.soc/1` maps. Its async frontdoor adapter must
have `read(address, width)` and `write(address, value, width)` methods. The
backdoor adapter uses the qualified register name in place of the address.
Frontdoor reads and writes apply access, read-clear and write-one-clear mirror
rules. Backdoor peek/poke use raw storage semantics. Unknown reset values keep
an unknown mirror until observed. A checked read cannot pass with an unknown
mirror. The project must implement actual HDL/VPI/DPI access.

Native evidence on Verilator 5.052 with pyuvm 4.0.1 and cocotb 2.1.0: one
fixture test passed, zero skipped, eight comparisons, twelve simulated ns.
The runner emitted C3. Unit tests cover missing/unexpected/mismatched data,
empty evidence, byte enables, bounds, retirement order and RAL mirror failure.
This fixture does not exercise CPU instructions, exceptions, interrupts, debug
mode, live Spike comparison or CPU RAL pins. Those remain open under #296.
