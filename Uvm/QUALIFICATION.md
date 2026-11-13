# SV UVM qualification matrix

This matrix records the supplied native evidence. It is not full language qualification.

CPU engine: Verilator 5.049 devel rev v5.048-26-g25d4827bd (mod).
Probe engine: Verilator 5.049 devel rev v5.048-26-g25d4827bd (mod).

| Test | Runs | Status | Scope or workaround |
|---|---:|---|---|
| spike_retirements | 2 | checked | six ADDI/MISA retirements per seed; bounded RTL fixture |
| spike_fault_detection | 1 | checked | destination corruption must fail |
| spike_state_fault_detection | 1 | checked | GPR snapshot corruption must fail |
| spike_csr_fault_detection | 1 | checked | CSR snapshot corruption must fail |
| SV randc | 1 | checked | qualify the selected constraint expression separately |
| SV transition | 1 | runtime_gap; ignored-feature warning | use pyuvm observed bins and rvw cov functional; do not infer transition coverage from compilation |
| Accellera HDL backdoor/VPI | 0 | not established | custom qualified backdoor or explicit observation interface |
| VexRiscv SV CPU environment | 0 | not established | use the qualified live pyuvm binding |

The CPU fixture uses pinned Accellera UVM with UVM_NO_DPI and a separate Spike DPI bridge.
The Python coverage path can export observed bins for UCIS round trips.
It does not turn unobserved transitions into covered bins.
Rerun the native CPU example and probes after an engine or source change.
