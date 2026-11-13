# Bounded coverage campaigns

## Device-enabled snapshot

Budget: 384 executions, default configuration, seed 17, at most four native
workers. This batch includes the structure variants' unchanged default sizes,
M/U PMP, precise interrupts, device guards and 25 monitors. All 384 runs pass
with zero monitor firings. Of these, 377 traces match Spike strictly. Three
masked-WFI traces match with one IRQ synchronization each. Four CLINT traces
match under the declared IRQ/MMIO policy in [devices.md](devices.md). The
separate live PLIC repeat also passes strictly and has no monitor firing.

All rows below use the same point set: 2,247 line points and 4,416 branch points.
RTL SHA-256: `046b1811e572f2ca02adf55a75114aad8274bb98696033451b128381d240d49e`.
The earlier 80.40% line result below has a different point set. These percentages
cannot be used as a same-source regression comparison.

| Cumulative source | Executions | Line hit/total | Line | Branch hit/total | Branch |
|---|---:|---:|---:|---:|---:|
| Existing smoke programs | 3 | 1382/2247 | 61.50% | 2958/4416 | 66.98% |
| Add pinned riscv-tests | 53 | 1701/2247 | 75.70% | 3479/4416 | 78.78% |
| Add generated PMP/WFI and precise IRQ programs | 304 | 1790/2247 | 79.66% | 3642/4416 | 82.47% |
| Add speculative faults and chained flushes | 306 | 1791/2247 | 79.71% | 3785/4416 | 85.71% |
| Add full-ROB software IRQ schedule | 307 | 1791/2247 | 79.71% | 3787/4416 | 85.76% |
| Add 72 M/U absent-supervisor cases | 379 | 1791/2247 | 79.71% | 3787/4416 | 85.76% |
| Add four CLINT cases and directed PLIC | 384 | 1795/2247 | 79.88% | 3787/4416 | 85.76% |
| ACT4 | NOT RUN | build rejected | not measured | build rejected | not measured |

The 72 new privilege cases strictly match all 3,060 instruction records and
2,988 retirements. They take 78 to 81 cycles each. They check absent SATP,
SFENCE.VMA and SRET in M/U under SUM, MXR, MPRV, TVM, TW and TSR settings.
They add architectural evidence without adding a new code point. The first
RV32 build exposed an RV64 exit store in the shared generator.
[PR #1469](https://github.com/riscPrint/risc-v-workstation/pull/1469) fixes it.
The assembler-backed unit tests build 102 RV32 programs.

The closure reports retain 1,231 unhit points after the generated baseline
and 1,081 after the directed, privilege and device additions. No exclusion or
unreachable declaration is used. Candidate suggestions are not measured hits.

| RTL module | Unhit line points | Unhit branch points |
|---|---:|---:|
| Core | 452 | 629 |
| MulDiv | 0 | 0 |

Only 2,519 of 6,663 points have source navigation links. The following view is
partial. The issue queue's one linked point is not its complete denominator.

| Logical region | Linked points | Unhit linked points |
|---|---:|---:|
| Rename | 373 | 11 |
| ROB commit | 159 | 8 |
| Issue selection | 1 | 0 |
| LSQ | 603 | 214 |
| Recovery | 68 | 1 |

The three directed probe plans qualify again on this batch. They observe a
full-ROB software interrupt, a discarded wrong-path fault and forwarding while
an older branch awaits recovery. Consecutive-cycle recovery remains unhit.
Other full-ROB IRQ sources, forwarding byte and age combinations, simultaneous
issue readiness and rename/free-list combinations remain open.

## ACT4 configuration limit

Read [ACT4.md](../../../docs/ACT4.md). A bounded Zifencei build attempt uses
ACT4 revision `56d40ab301dba23dd3104c17bd969afbaaea1931`, Sail 0.15 and GCC
15.1.0. It reuses the instruction-only M-mode bootstrap. It does not remove a
test body or signature check. UDB 0.1.17 rejects NUM_PMP_ENTRIES=4 during
configuration validation. Zero ELFs build. No DUT test runs. The profile keeps
the real four-entry count. No ACT4 result is inferred from another suite.

The first attempt also found the documented macOS Z3 library setup problem.
The private-cache workaround fixes that setup error. It does not fix the PMP
configuration rejection. Repeat the attempt with a private pinned checkout:

```sh
nice -n 10 "$RVW_HOME/rvw/.venv/bin/python" rvw/act4-attempt.py \
  --checkout "$ACT4_CHECKOUT" --out rvw/out/act4-attempt \
  --z3-library /opt/homebrew/opt/z3/lib/libz3.dylib
```

The script returns failure when no tests build. It runs no DUT simulation.
Standard Sm qualification and ACT4 coverage remain open.

## Reproduce the extended batch

Use the prerequisites below and fresh output paths. Run from the core project.
Set RVW_HOME, RVW_SBT_LOCK=sbt-ooomini2 and RVW_OOO_LOCK=ooo-mini-ooomini2.

```sh
"$RVW_HOME/rvw/.venv/bin/rvw" regress privilege build rvw/privilege-mu32.json \
  --out rvw/out/disabled-mu32
nice -n 10 "$RVW_HOME/rvw/.venv/bin/python" rvw/coverage-campaign.py --extended
nice -n 10 "$RVW_HOME/rvw/.venv/bin/python" rvw/check-devices.py --coverage \
  --out rvw/out/coverage-device-plugins
nice -n 10 "$RVW_HOME/rvw/.venv/bin/python" rvw/coverage-analysis.py --extended
```

The campaign reuses the strict comparison and probe qualifiers. Device checks
include the live PLIC repeat. That duplicate is outside the 384-run coverage
merge. Raw reports, manifests, coverage dumps and candidates stay in rvw/out.

## Initial M/U PMP snapshot

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

ACT4 was not attempted in this initial batch. The later bounded attempt above
records the four-entry PMP configuration rejection.

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
