# External debug integration decision

| Check | Result |
|---|---|
| Existing Debug Module or DMI/JTAG port | Absent |
| Retirement halt signal | `r.halt := False` in `Core.scala` |
| Precise store boundary | Stores update memory at ROB commit |
| Halt/resume/step command input | Absent |
| Abstract GPR/CSR access while halted | Absent |
| Decision | Skip the optional third-core integration |
| Native debug campaigns | NOT RUN |

Adding the SpinalHDL Debug Module is not sufficient. The core needs a debug
state machine at commit, a rule for younger ROB entries, a stopped register
and CSR access path, DPC/DCSR state, and a precise resume/step path. These are
core changes. They exceed a small extra example configuration. The current
retirement probes do not implement this control path. No default configuration
or core source was changed for this decision.
