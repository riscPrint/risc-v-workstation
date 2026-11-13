# Absolute IPC error diagnosis

The occupancy policy adds most of the held-out absolute error. It also moves
prediction from issue to rename. This is a composite policy change. The table
does not isolate filler occupancy from prediction timing. All five retained
stages use one engine and the same fitted parameters. No variant selects a
parameter. The earlier resource study retains all 24 pairs for each stage.

Signed base IPC error, in percent. Positive means that the model is too fast.

| Held-out program | Baseline | Prediction and occupancy | Plus drain | Plus order window | Old global cache retry |
|---|---:|---:|---:|---:|---:|
| towers | +20.34 | +19.92 | +19.95 | +19.81 | +19.81 |
| vvadd | +7.99 | +10.45 | +10.45 | +10.45 | -5.93 |
| rsort | +0.57 | +1.43 | +1.25 | +1.23 | -2.64 |
| memcpy | -8.14 | +9.69 | +9.69 | +9.69 | -14.74 |
| dhrystone | -0.75 | -1.46 | -1.59 | -1.60 | -1.64 |
| spmv | -7.03 | -11.70 | -11.70 | -11.70 | -12.51 |

Mean held-out absolute error rises from 7.47% to 9.11% with the composite
occupancy policy. Drain leaves the rounded mean unchanged. The order window
reduces it to 9.08%. The old global cache retry raises it to 9.55%.

The largest added absolute errors from occupancy are spmv, vvadd and memcpy.
Memcpy also changes error sign. Its predicted IPC becomes too high. The
occupancy policy reduces its issue-full count from 11,495 to 2,707. It also
changes branch misses from 36 to 52. These are model schedule changes. They
do not prove a hardware cause for the error.

The branch penalty is an effective fitted value. It can absorb missing
prediction, recovery and front-end behavior. A new directed base capture
also shows that a memory-order detection-to-restart span includes commit
waiting. Treating either value as an extracted execution latency is wrong.
Cost isolation remains open.

The model now preserves instructions between the detecting store and the
oldest violating load. The prior window invalidated those instructions.
A targeted schedule checks that this independent work executes once. The
NaxRiscv directed capture uses the violating load as its inclusive flush
anchor. This fixes a recovery-window error. It does not establish restoration
of the 7.47% held-out mean. No per-variant tuning is applied.

[The retained data](absolute-diagnosis-results.json) gives each signed error,
the added absolute error by stage, source hashes and the branch-miss and issue-full counter pairs.
Exact local retry overhead and speculative predictor history remain open.

## Commit waiting and remaining regression

The new commit policy predicts the wait for the violating load to reach
commit. It uses one measured restart cycle. It does not charge the full
seven-cycle detection-to-restart span as a fixed penalty. No variant or
held-out result selects a cost. Local extra costs remain assumed zero.

| Policy | Within / 24 | Nonzero within / 15 | Training MAE (%) | Held-out MAE (%) |
|---|---:|---:|---:|---:|
| Typed immediate window | 15 | 6 | 7.31 | 9.05 |
| Commit-controlled window | 14 | 5 | 7.31 | 8.82 |
| Commit window with local cache retry | 11 | 2 | 7.39 | 7.29 |

| Held-out program | Typed immediate error (%) | Commit-controlled error (%) | Predicted commit wait cycles |
|---|---:|---:|---:|
| towers | +19.677 | +18.242 | 18 |
| vvadd | +10.453 | +10.453 | 0 |
| rsort | +1.229 | +1.227 | 57 |
| memcpy | +9.687 | +9.687 | 0 |
| dhrystone | -1.583 | -1.630 | 6 |
| spmv | -11.699 | -11.705 | 18 |

The missing commit-wait mechanism accounts for part of the error. Towers
improves. Vvadd and memcpy do not change. Dhrystone and spmv regress slightly.
The LQ8 towers pair leaves the size criterion. The full held-out regression
from the earlier 7.47% mean is not resolved by the cache-disabled policy.

Local cache retry lowers the mean to 7.29%, but only 11/24 deltas meet the
criterion. It remains disabled. These results provide no policy that
improves both delta coverage and absolute error. Do not tune individual
variants to hide this tradeoff. Speculative prediction, local retry cost
isolation and exact cache retry predicates remain open.

The five historical stages above share one recorded engine. The new commit
candidates share another recorded engine. The typed immediate result uses
its prior engine snapshot. The retained records identify both versions.
These are retrospective comparisons on the same frozen RTL captures.

[Commit policy data](commit-replay-results.json) and
[rejected cache data](commit-cache-results.json) retain each delta, absolute
error, event count and engine identity. Configurations are
[ooo-commit-replay.json](ooo-commit-replay.json) and
[ooo-commit-cache.json](ooo-commit-cache.json).
