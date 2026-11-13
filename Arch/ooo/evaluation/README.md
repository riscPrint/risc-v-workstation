# Default workload sample

These are complete Spike traces and sampled model timings. All seven
program output checks passed. Model accuracy remains inconclusive.
The sample uses up to three 2,000-instruction points and 200 warmup
instructions per point. Sampling error against full timing is NOT MEASURED.

| Workload | Trace instructions | Zen-5-like IPC | M1-like IPC |
|---|---:|---:|---:|
| crc32 | 3,831,528 | 0.4595 | 0.4595 |
| matmult-int | 3,196,262 | 0.3619 | 0.3619 |
| slre | 2,507,947 | 0.4334 | 0.4334 |
| coremark-smoke | 2,742,559 | 0.5167 | 0.5210 |
| qsort | 228,696 | 0.3066 | 0.3066 |
| rsort | 368,194 | 0.7094 | 0.7094 |
| zstd-roundtrip | 17,851,075 | 0.5660 | 0.5660 |

Six saved sampled results were reused. The resumed worker completed zstd
sampling with the same settings. The reference models share fixed latencies
and sequential prediction. Capacity changes can therefore leave IPC equal.
These are RISC-V timing experiments, not commercial CPU emulation.

See [input hashes, pinned revisions and per-point timing](results.json).

The resumed zstd M1-like run reuses source windows after the first complete
validation. Raw byte hashes are checked before and after extraction. Each
reused window must reproduce the complete-validation Zen-5-like timing.
The [campaign helper](reuse-validated-windows.py) records this reuse in the
M1-like report. The regular evaluation command validates each model input.

## Shared validation check

The evaluator now shares complete validation and decoded windows across
compatible models. On the 3,831,528-instruction CRC32 source, one validation
call produced both reports. Both reports exactly match the saved independent
runs. This check measures validation calls, not wall-time speedup.
See [the source hashes and result](shared-validation.json).
