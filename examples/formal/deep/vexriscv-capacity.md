# VexRiscv compiled property capacity

Measured on macOS ARM64 on 2026-11-13. The run used 43 existing generated riscv-formal safety models. The cover task was excluded. Each source model hash is in `vexriscv-capacity-results.json`. Raw artifacts are in `out/deep-capacity`. No core build ran. At most three jobs ran at nice priority.

Baseline jobs had an eight-second total SBY limit. Variant jobs had a four-second total SBY limit. Preparation is included. The different limits prevent a paired speed comparison. The source restrictions and fixed check cycle remain unqualified. A safety engine does not turn the named liveness check into an unbounded progress proof.

| Engine | Qualified solved / unsolved | Timeout | Native inconclusive | Total wall seconds |
|---|---:|---:|---:|---:|
| abc:pdr | 0 / 43 | 43 | 0 | 347.419 |
| aiger:rIC3 | 0 / 43 | 43 | 0 | 346.739 |
| smtbmc:yices | 0 / 43 | 29 | 14 | 331.925 |

| Variant | Qualified solved / unsolved | Native observations | Total wall seconds |
|---|---:|---|---:|
| ram | 0 / 43 | {'timeout': 43} | 181.583 |
| counter | 0 / 43 | {'timeout': 43} | 181.900 |
| uf | 0 / 43 | {'not_applicable': 35, 'inconclusive': 8} | 35.870 |
| cut-points | 0 / 43 | {'fail': 5, 'error': 38} | 105.175 |

RAM cuts remove complete memory outputs. Counter variants cut all adder outputs. This is broader than a counter quotient certificate. State cuts remove flip-flop outputs. The five native state-cut failures remain abstraction observations. The other 38 state-cut jobs failed during SBY witness reconstruction with a signal mismatch. No concrete DUT failure is claimed.

UF used the existing global SMT uninterpreted-function wrapper on the eight models with multiply cells. The other 35 have no matching arithmetic cell. No variant earned a qualified solve. This run therefore shows no measured capacity gain. It does not establish that a longer budget or refined abstraction cannot help.

The inspected example has generated riscv-formal checks and simulation CSR monitors. It has no committed generated formal autocheck, protocol or CSR property bundle to add to this campaign. Those requested property classes remain NOT RUN. Creating and binding those sets needs the owning generation flow. Counter leaf quotient binding also remains unimplemented for these flattened core models.
