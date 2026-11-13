# Ibex findings

| Scope | Observation | Classification |
| --- | --- | --- |
| Standard riscv-tests bootstrap | Writes arbitrary continuation addresses to mtvec. Ibex requires 256-byte alignment. Traps restart the boot region. | Platform bootstrap mismatch. Instruction profile uses an explicit reduced bootstrap. |
| RVFI masks | Non-memory records can have read mask 15. | Transport convention. Exporter gates inactive masks and retains the raw values. |
| RVFI order | First valid retirement has order 1. | Transport origin. Exporter validates the sequence and subtracts 1. |
| Slang with RVFI | Cross-module references to counters conflict with preserved hierarchy. | Query limit. Navigation omits RVFI instrumentation and retains the whole functional core. |

No core defect is established by these observations. Strict comparison results
and qualification limits must be read separately from C1 program completion.
