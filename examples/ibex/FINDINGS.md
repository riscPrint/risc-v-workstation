# Ibex findings

| Scope | Observation | Classification |
| --- | --- | --- |
| ACT4 generated configuration | A shared `rvw-act4` UDB name supplied an RV64/F header for the RV32IMC input. | Tool cache bug. The generic builder now names the architecture from its extension and parameter hash. The compiler failure was not a DUT result. |
| ACT4 model inputs | Counter masks, breakpoint mtval, MENVCFG FIOM, compressed support and U-mode WFI differed from the RTL. | Reference profile settings. The corrected profile gives 148/148 C1 passes with the standard Sm bootstrap. No test-body access was removed. |
| Captured ELF | The adapter used `nm` to reread the original ELF for `tohost`. | Input capture bug. The adapter now reads symbols from the same captured bytes used for RAM and identity. |
| Native header identity | Device-model header bytes were absent from the compiler-unit list. | Generic identity gap. Optional `harness_inputs` now hashes non-compilation inputs. A changed header changes the model identity. |
| Misaligned scalar RAM | `rv32ui-p-ma_data` first differs at `lh t2,1(s0)` under the default trap policy. Ibex completes the access. | Platform setting. `misaligned: emulate` and `scalar_split_ram: true` give a complete strict match. |
| Standard riscv-tests bootstrap | Writes arbitrary continuation addresses to mtvec. Ibex requires 256-byte alignment. Traps restart the boot region. | Platform bootstrap mismatch. Instruction profile uses an explicit reduced bootstrap. |
| RVFI masks | Non-memory records can have read mask 15. | Transport convention. Exporter gates inactive masks and retains the raw values. |
| RVFI order | First valid retirement has order 1. | Transport origin. Exporter validates the sequence and subtracts 1. |
| Slang with RVFI | Cross-module references to counters conflict with preserved hierarchy. | Query limit. Navigation omits RVFI instrumentation and retains the whole functional core. |

No core defect is established by these observations. Strict comparison results
and qualification limits must be read separately from C1 program completion.
