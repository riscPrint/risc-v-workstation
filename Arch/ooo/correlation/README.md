# RTL correlation experiment

This experiment uses the example's real RTL adapters. It does not use gem5.
The six programs have different ELF hashes. Chain, multiply and memory form
the training set. Independent, divide and branch form the held-out set.
Each kernel runs 200 iterations. C1 and C2 cover startup through the retired
`tohost` store. Seed is 1. Fixed memory latency is zero.

Prepare the ELFs and native manifests:

```sh
python Arch/ooo/correlation/prepare.py OUT
```

Source the native environment. Select a private external core copy with
`VEXRISCV` or `VEXIIRISCV`. Set `RVW_HOME` to this checkout. Set
`RVW_VEX_LOCK=vex-arch`. Set `RISCVSIM_WORK` to a private output directory.
Run each adapter with `nice -n 10`:

```sh
examples/vexriscv/rvw/run.sh run-many --manifest OUT/vexriscv.jsonl --jobs 1 --json
examples/vexiiriscv/rvw/run.sh run-many --manifest OUT/vexiiriscv.jsonl --jobs 1 --json
python Arch/ooo/correlation/score.py OUT vexriscv
python Arch/ooo/correlation/score.py OUT vexiiriscv
python Arch/ooo/correlation/summarize.py OUT results.json
```

The scorer converts VexRiscv probe counters with `rvw probes convert --to counts`.
It checks C1/C2 identity and whole-program instruction counts. It then runs
`rvw arch ooo-fit` on a 16-point grid. Selection uses mean absolute relative
cycle error and mapped branch-count error on training programs only.
IPC error is `100 * (model IPC / RTL IPC - 1)`.

The model's single-issue in-order queue prevents younger instructions from
passing an older blocked instruction. Fetch and execution can overlap. It
still uses a simplified pipeline, fixed execution latencies and sequential
branch prediction. VexRiscv uses STATIC prediction. Thus the fitted branch
penalty can absorb predictor and fetch-policy differences. It is not an
extracted RTL parameter. Several training kernels can have equal RTL cycles.
The grid cannot uniquely identify all pipeline parameters from these samples.

VexiiRiscv has no SpinalProbes binding in this example. Its score is IPC-only.
An empty event map does not turn missing event measurements into zero counts.
Neither experiment has enough held-out programs and event families for the
existing coverage budget. Neither experiment establishes application accuracy.
Raw C1, C2, probe streams and fitting candidates stay in OUT. The compact
results retain input hashes. No repeatability interval is inferred from one run.

## Native sample on 2026-11-13

Both RTL batches passed all six programs. These are whole-program IPC values.

| Core | Program | Split | RTL cycles | RTL IPC | Base IPC error | Fitted IPC error |
|---|---|---|---:|---:|---:|---:|
| vexriscv | chain | training | 3638 | 0.2776 | +50.52% | +3.41% |
| vexriscv | multiply | training | 3638 | 0.2776 | +50.52% | +3.41% |
| vexriscv | memory | training | 3638 | 0.2776 | +50.52% | +3.41% |
| vexriscv | independent | heldout | 3638 | 0.2776 | +50.52% | +3.41% |
| vexriscv | divide | heldout | 10038 | 0.1006 | +22.18% | +11.34% |
| vexriscv | branch | heldout | 4238 | 0.2619 | +33.82% | -6.20% |
| vexiiriscv | chain | training | 4058 | 0.2491 | +67.69% | +26.18% |
| vexiiriscv | multiply | training | 3058 | 0.3306 | +26.36% | -4.91% |
| vexiiriscv | memory | training | 3262 | 0.3099 | +34.85% | +1.46% |
| vexiiriscv | independent | heldout | 2458 | 0.4113 | +1.57% | -23.57% |
| vexiiriscv | divide | heldout | 6298 | 0.1605 | -23.36% | -30.13% |
| vexiiriscv | branch | heldout | 4158 | 0.2672 | +31.17% | -4.76% |

VexRiscv selects fetch latency 4 and branch penalty 7. VexiiRiscv selects
fetch latency 3 and branch penalty 7.
The grid has fetch latencies 1, 2, 3, 4 and branch penalties 1, 3, 5, 7.
VexRiscv branch counts agree on all six programs. No VexiiRiscv event
comparison was run. The fitted VexRiscv divide error remains outside 10%.
These results are approximate model measurements, not a fidelity verdict.
See [the compact input hashes and values](results.json).

## Static predictor correction

The current VexRiscv description uses decoded STATIC targets. The cacheless
VexiiRiscv description stays sequential. Its cached config adds BTB, GShare
and RAS and needs a separate description. No dynamic predictor fit is claimed.

The saved native runs above were reused. RTL was not rerun. Training alone
selects fetch latency 7 and branch penalty 7 from fetch latencies 3, 5, 7, 9
and penalties 1, 3, 5, 7. The old table remains a historical sequential model.

| Program | Split | Model misses | RTL misses | Base IPC error | Fitted IPC error |
|---|---|---:|---:|---:|---:|
| chain | training | 1 | 1 | +99.56% | +2.62% |
| multiply | training | 1 | 1 | +99.56% | +2.62% |
| memory | training | 1 | 1 | +99.56% | +2.62% |
| independent | heldout | 1 | 1 | +99.56% | +2.62% |
| divide | heldout | 1 | 1 | +31.70% | +31.35% |
| branch | heldout | 101 | 101 | +64.71% | -2.46% |

The six miss counts now agree. This does not establish agreement on larger
programs. The held-out divide error is +31.35%. Static prediction removes a
compensating error in the old fit. Pipeline and divide timing still need work.
See [the corrected values and input hashes](results-static.json).
