# Measured Scala DSL properties

Native run on 2026-11-13. VexRiscv revision `a62c145a`, SpinalHDL 1.15.0,
Verilator 5.049 and SMTBMC/Yices. All 49 aligned ISA programs passed.
The table sums counts across those programs. Formal used three workers.
All 34 assertions returned bounded passes at depth 12. Separate bounded
antecedent covers reached 33 of 34 antecedents. The last-stage stall antecedent
was not reached within 12 cycles. This does not prove that it is unreachable.

The prior safety campaign restored 34 of 34 observations from the exact cache.
A native activation-cache fixture also restored its cover witness files.

Pass counts include false antecedents. Activation counts are separate.
Six assertion antecedents had zero simulation matches. Five concern data-bus
stalling. The sixth is the last-stage stall. Formal reached the five data-bus
antecedents. The current ISA memory model does not exercise these stalls.

Formal assumes two reset clocks. Other inputs are arbitrary. No full proof,
liveness proof or hardware result is claimed. Source lines identify DSL calls.

| Property | DSL line | Sim pass | Sim fail | Sim active | Sim cover | Formal | Antecedent cover |
|---|---:|---:|---:|---:|---:|---|---|
| `stage0_fire_valid` | 38 | 42769 | 0 | 17931 | 0 | bounded 12 | reached |
| `stage0_fire_not_stuck` | 39 | 42769 | 0 | 17931 | 0 | bounded 12 | reached |
| `stage0_fire_not_removed` | 40 | 42769 | 0 | 17931 | 0 | bounded 12 | reached |
| `stage0_stall_pc` | 41 | 42720 | 0 | 1546 | 0 | bounded 12 | reached |
| `stage1_fire_valid` | 38 | 42769 | 0 | 17735 | 0 | bounded 12 | reached |
| `stage1_fire_not_stuck` | 39 | 42769 | 0 | 17735 | 0 | bounded 12 | reached |
| `stage1_fire_not_removed` | 40 | 42769 | 0 | 17735 | 0 | bounded 12 | reached |
| `stage1_stall_pc` | 41 | 42720 | 0 | 588 | 0 | bounded 12 | reached |
| `stage2_fire_valid` | 38 | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage2_fire_not_stuck` | 39 | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage2_fire_not_removed` | 40 | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage2_stall_pc` | 41 | 42720 | 0 | 1188 | 0 | bounded 12 | reached |
| `stage3_fire_valid` | 38 | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage3_fire_not_stuck` | 39 | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage3_fire_not_removed` | 40 | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage3_stall_pc` | 41 | 42720 | 0 | 0 | 0 | bounded 12 | not_reached_within_bound |
| `pc_chain_0` | 45 | 42720 | 0 | 17931 | 0 | bounded 12 | reached |
| `pc_chain_1` | 45 | 42720 | 0 | 17735 | 0 | bounded 12 | reached |
| `pc_chain_2` | 45 | 42720 | 0 | 17686 | 0 | bounded 12 | reached |
| `ibus_hold_valid` | 49 | 42720 | 0 | 19737 | 0 | bounded 12 | reached |
| `ibus_hold_pc` | 50 | 42720 | 0 | 19737 | 0 | bounded 12 | reached |
| `ibus_pc_aligned` | 51 | 42769 | 0 | 40196 | 0 | bounded 12 | reached |
| `dbus_hold_valid` | 58 | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `dbus_hold_address` | 59 | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `dbus_hold_data` | 60 | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `dbus_hold_write` | 61 | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `dbus_hold_size` | 62 | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `x0_write_zero` | 66 | 42769 | 0 | 4747 | 0 | bounded 12 | reached |
| `retire_machine` | 67 | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `retire_rv32` | 68 | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `retire_pc_aligned` | 69 | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `trap_mie_clear` | 78 | 42769 | 0 | 196 | 0 | bounded 12 | reached |
| `trap_mpp_machine` | 79 | 42769 | 0 | 196 | 0 | bounded 12 | reached |
| `trap_mepc_aligned` | 80 | 42769 | 0 | 196 | 0 | bounded 12 | reached |
| `retirement_reached` | 81 | 0 | 0 | 0 | 17686 | NOT RUN: cover | NOT RUN |
| `trap_reached` | 82 | 0 | 0 | 0 | 196 | NOT RUN: cover | NOT RUN |

All source lines refer to `rvw/src/main/scala/rvwvex/CoreProperties.scala`.

The fetched-instruction identity and eventual retirement or flush property
remains unimplemented. Bus-response accounting and masked register-file storage
checks also remain open. The current register checks observe RVFI write rules.

A deliberately false retirement assertion failed in the prior native `add`
campaign. The program still reached `tohost=1`. C1 retained the assertion failure.
The seeded assertion is a test fixture. It is not a discovered core defect.
