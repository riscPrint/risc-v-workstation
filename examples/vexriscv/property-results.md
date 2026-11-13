# Measured Scala DSL properties

Native run on 2026-11-13. VexRiscv revision `a62c145a`, SpinalHDL 1.15.0,
Verilator 5.049 and SMTBMC/Yices. All 49 aligned ISA programs passed.
The table sums counts across those programs. Formal used three workers.
All 34 assertions returned bounded passes at depth 12. A second exact run
restored all 34 observations from the cache. C3 and JUnit retained the bounds.

Pass counts include false antecedents. Antecedent reachability is not measured.
Formal assumes two reset clocks. Other inputs are arbitrary. No full proof,
liveness proof or hardware result is claimed.

| Property | Sim pass | Sim fail | Sim cover | Formal |
|---|---:|---:|---:|---|
| `stage0_fire_valid` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage0_fire_not_stuck` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage0_fire_not_removed` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage0_stall_pc` | 42720 | 0 | 0 | bounded 12; cache hit |
| `stage1_fire_valid` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage1_fire_not_stuck` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage1_fire_not_removed` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage1_stall_pc` | 42720 | 0 | 0 | bounded 12; cache hit |
| `stage2_fire_valid` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage2_fire_not_stuck` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage2_fire_not_removed` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage2_stall_pc` | 42720 | 0 | 0 | bounded 12; cache hit |
| `stage3_fire_valid` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage3_fire_not_stuck` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage3_fire_not_removed` | 42769 | 0 | 0 | bounded 12; cache hit |
| `stage3_stall_pc` | 42720 | 0 | 0 | bounded 12; cache hit |
| `pc_chain_0` | 42720 | 0 | 0 | bounded 12; cache hit |
| `pc_chain_1` | 42720 | 0 | 0 | bounded 12; cache hit |
| `pc_chain_2` | 42720 | 0 | 0 | bounded 12; cache hit |
| `ibus_hold_valid` | 42720 | 0 | 0 | bounded 12; cache hit |
| `ibus_hold_pc` | 42720 | 0 | 0 | bounded 12; cache hit |
| `ibus_pc_aligned` | 42769 | 0 | 0 | bounded 12; cache hit |
| `dbus_hold_valid` | 42720 | 0 | 0 | bounded 12; cache hit |
| `dbus_hold_address` | 42720 | 0 | 0 | bounded 12; cache hit |
| `dbus_hold_data` | 42720 | 0 | 0 | bounded 12; cache hit |
| `dbus_hold_write` | 42720 | 0 | 0 | bounded 12; cache hit |
| `dbus_hold_size` | 42720 | 0 | 0 | bounded 12; cache hit |
| `x0_write_zero` | 42769 | 0 | 0 | bounded 12; cache hit |
| `retire_machine` | 42769 | 0 | 0 | bounded 12; cache hit |
| `retire_rv32` | 42769 | 0 | 0 | bounded 12; cache hit |
| `retire_pc_aligned` | 42769 | 0 | 0 | bounded 12; cache hit |
| `trap_mie_clear` | 42769 | 0 | 0 | bounded 12; cache hit |
| `trap_mpp_machine` | 42769 | 0 | 0 | bounded 12; cache hit |
| `trap_mepc_aligned` | 42769 | 0 | 0 | bounded 12; cache hit |
| `retirement_reached` | 0 | 0 | 17686 | NOT RUN: cover |
| `trap_reached` | 0 | 0 | 196 | NOT RUN: cover |

The fetched-instruction identity and eventual retirement or flush property
remains unimplemented. Bus-response accounting and masked register-file storage
checks also remain open. The current register checks observe RVFI write rules.

A deliberately false retirement assertion failed in the native `add` program.
The program still reached `tohost=1`. C1 retained the assertion failure.
The seeded assertion is a test fixture. It is not a discovered core defect.
