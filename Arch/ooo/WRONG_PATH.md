# Bounded Spike wrong-path experiment

`rvw arch ooo-wrong-path CONFIG TRACE --elf ELF --platform PLATFORM
--out NEW_DIRECTORY --json` captures real speculative bytes from Spike.
The MCP tool is `arch_ooo_wrong_path`. It is a cancellable job.

The additive primary shim API redirects PC. The replay add-on creates a
checkpoint from the initial machine inputs and an append-only action history.
Restore creates a new Spike machine, replays the saved prefix and checks
every effect hash. It restores architectural state by functional replay.
It does not copy Spike internals or create an RTL checkpoint. Restore cost
grows with the committed prefix. Only one hart is supported. External entropy
and custom extensions are refused.

The experiment compares PC, next PC, instruction and privilege mode with C2.
It also compares integer register writes and memory effects. FP register
effects are not compared by this capture checker. It captures up to
16 wrong-path instructions for each selected sequential-prediction miss.
Wrong operations use shared ROB, issue, register and memory resources. They
squash at branch resolution. Wrong stores do not change cache or memory.
Loads can change cache state. Correct-target lookahead is stopped.

## Native sample

These two small RV32IM programs use a two-wide model, a six-cycle branch
latency, a three-cycle recovery cost and a 4 KiB two-way data cache. The
configuration is an experiment, not the VexRiscv RTL pipeline description.
All misses under sequential prediction were captured. Wrong-path instruction windows stay bounded.

| Program | Captured misses | Baseline cycles | Wrong-path cycles | Baseline IPC error |
|---|---:|---:|---:|---:|
| branch | 299 | 3878 | 4628 | +19.34% |
| memory | 199 | 3012 | 2608 | -13.41% |

The error is `100 * (baseline IPC / wrong-path IPC - 1)`. It compares two
model policies. It is not measured error against RTL and is not an error
bound. The gap also includes removal of correct-target lookahead. Wrong
loads can act as prefetches, so the sign can differ across programs.

Predictor history repair, dynamic targets, nested prediction, wrong-store
cache effects and uop-cache pollution remain unsupported. Fetch requests
are batched at branch issue. The default committed-path model is unchanged.

The native controls restore PC, GPRs, memory, mscratch and minstret. They
also reject a nondeterministic history. See [configuration and hashes](wrongpath-results.json).
