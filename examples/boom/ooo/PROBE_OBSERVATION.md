# Native probe and timing observation

All runs used small, seed 1, the BOOM lock and nice priority 15.
The adapter adds probes. It does not change core sources.
`PROBE_OBSERVATION.json` records counters, stall causes and capture hashes.
Raw captures remain in the local run directory.

The capture tests passed on beq, fadd, SFB and timing: 8 tests passed.
The first capture failed the prediction regression. ROB repair overwrites
`uop.taken`. The corrected binding retains the enqueue prediction.
There were two native builds in this continuation. The corrected build
uses `-O0`. No regression suite or BOOM formal job ran.

| Program | RTL cycles | C1 instructions | RTL IPC | Model cycles | Model IPC | Model / RTL IPC |
|---|---:|---:|---:|---:|---:|---:|
| Timing loop | 258 | 57 | 0.22093 | 96 | 0.59375 | 2.6875 |
| SFB loop | 314 | 84 | 0.26752 | 160 | 0.52500 | 1.9625 |

These are whole-program regions, including startup. There is no fitting.
`rvw arch ooo-calibrate` used timing as training and SFB as held-out input.
It reports accuracy `inconclusive`. The OoO model refuses the ISA traces
because they contain traps. Do not remove traps to claim a whole-run match.

| Conditional branches | Events | RTL direction misses | Model direction misses | Direction disagreements |
|---|---:|---:|---:|---:|
| beq | 76 | 45 | 43 | 62 |
| fadd | 25 | 21 | 5 | 24 |
| SFB | 33 | 14 | 5 | 9 |

`rvw csim compare-rtl` used `examples/boom/csim/tage-l.json` and branch events
converted from `conditional_commit_0`. Its status is `compared`. The model
is approximate. A comparison report is not a predictor fidelity verdict.

The SFB loop passed its arithmetic check. It recorded 92 ROB commits:
85 architectural and 7 predicated off. C1 and C2 contain 84 instructions.
The probe sampling window therefore contains one more architectural commit.
Endpoint alignment remains open. The predicated-off count is separate from
architectural retirement. Refs: #49.

For the timing loop, calibration reports 57 model issues and 57 architectural
commit samples. RTL has 7 correction pulses; the model has 3 branch misses.
For SFB, the corresponding counts are 84 versus 85 and 7 versus 7.
Equal correction totals do not establish equal speculative behaviour.

Perf reports measured D-cache nack and dispatch-blocked samples. For timing,
these are 1 and 6 cycles. It leaves 134 zero-retirement cycles unattributed.
For SFB, these are 2 and 6 cycles, with 156 unattributed cycles. Causes can
overlap. This is bounded stall attribution, not complete pipeline coverage.
I-TLB misses and PTW activity remain unexercised in these bare-mode programs.
See `RiscvSim/boom/PROBE_BINDINGS.md` for units and source limits.
