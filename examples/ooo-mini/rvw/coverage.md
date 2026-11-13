# Bounded coverage campaign

Budget: one batch of 306 ELF executions, seed 17, default configuration,
four workers, no random search or proof exclusions. Every run passes. All
22 native monitors stay clear. All 50 ISA traces match Spike strictly.
Across the batch, 303 traces match strictly. The three masked-WFI traces
match with one IRQ synchronization each. No other synchronization is enabled.

## Coverage after each source of tests

These rows use one instrumented model with 2,066 line points and 4,070 branch
points. The historical 60.24% result predates U-mode/PMP and has a different
point universe. It is not a same-source baseline.

| Cumulative source | Programs | Line hit/total | Line | Branch hit/total | Branch |
|---|---:|---:|---:|---:|---:|
| Existing smoke, self-modifying code and illegal instructions | 3 | 1277/2066 | 61.81% | 2762/4070 | 67.86% |
| Add pinned riscv-tests RV32UI/M | 53 | 1579/2066 | 76.43% | 3253/4070 | 79.93% |
| Add generated PMP/WFI and precise-interrupt programs | 304 | 1660/2066 | 80.35% | 3381/4070 | 83.07% |
| Add speculative protection and chained flush programs | 306 | 1661/2066 | 80.40% | 3485/4070 | 85.63% |
| ACT4 | NOT RUN | not measured | not measured | not measured | not measured |

ACT4 setup and long builds exceed the worker brief's permitted short runs.
No ACT4 result is inferred from riscv-tests. See [ACT4](../../../docs/ACT4.md).

The closure tool reports 1,095 unhit points before the final two programs and
990 after them. It applies project-declared candidates to source-linked control
paths. Candidate suggestions are not measured hits. The raw reports, candidates
and source hashes stay under rvw/out/coverage-analysis.

## Remaining holes

| RTL module | Unhit line points | Unhit branch points |
|---|---:|---:|
| Core | 405 | 585 |
| MulDiv | 0 | 0 |

Rename, ROB, issue queue, LSQ and recovery are logical regions inside Core.
They are not separate RTL modules. The source navigation links give this partial
view. A link does not establish a source statement hit or a complete block
denominator. The issue queue's one linked point cannot establish queue coverage.

| Logical region | Linked code points | Unhit linked points |
|---|---:|---:|
| Rename allocation | 365 | 11 |
| ROB commit | 159 | 8 |
| Issue selection | 1 | 0 |
| LSQ and forwarding | 601 | 222 |
| Recovery | 68 | 1 |

Only 2,309 of 6,136 code points have source navigation links. The unlinked points
remain in the real totals. No point is waived or declared unreachable.

## Directed priorities

| Program | Case and self-check | Evidence limit |
|---|---|---|
| interrupt-precise.S, three sources | Interrupt during division and memory work. Check cause, PC interval, zero mtval, MIE/MPIE and return. | ROB-full coincidence and interrupt/forward overlap are not established by C2. |
| protection-speculative.S | An older divide holds the head while a branch discards younger denied accesses. Later U loads/stores trap precisely. Check handler count, exact fault PCs and unchanged protected RAM. | C2 proves the architectural outcome. A separate probe sequence must establish which wrong-path accesses issued. |
| flush-chain.S | Four rounds of branch recovery, FENCE.I, ECALL, MRET and mstatus serialization, with store/load checks. | Consecutive-cycle flush is impossible while the ROB is empty after recovery. Other close flush sequences need explicit probe goals. |

No current result establishes all rename/free-list combinations, ROB-full
interrupt entry, simultaneous readiness transitions at issue, every forwarding
lane/age combination, or every recovery overlap. These are open functional goals,
not conclusions that the associated code is unreachable.

## Reproduce

Build the prerequisite suites with check-interrupts.py, check-protection.py,
build-programs.sh and build-isa.py as described in the other notes. Use the
pinned riscv-tests revision recorded by build-isa.py. Then run from the project:

```sh
nice -n 10 "$RVW_HOME/rvw/.venv/bin/python" rvw/coverage-campaign.py
nice -n 10 "$RVW_HOME/rvw/.venv/bin/python" rvw/coverage-analysis.py
```

The first command needs fresh coverage-runs output paths. The second regenerates
all four reports and both closure reports. Raw data and generated candidate IDs
stay out of version control.
