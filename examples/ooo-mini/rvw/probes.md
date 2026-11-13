# Protection and recovery probe campaign

This snapshot has 24 native monitors. The later device increment adds a
head-only MMIO load monitor, for 25 total. See [device checks](devices.md)
for its full regression and repeated goal qualification. The new checks require privilege 0 or 3
and recheck store permission at commit. Probe-only state measures recovery
spacing. It is absent when probes are disabled. Default dimensions and module
names remain unchanged.

| Run set | RTL | Strict Spike | Explicit synchronization | Monitor firings |
|---|---|---|---|---|
| Fixed suites plus a full-ROB interrupt schedule | 307/307 pass | 304 complete matches | Three masked-WFI cases match with one IRQ synchronization each | Zero, 24 monitors |

The 307 executions use 306 ELFs. One interrupt ELF runs with another schedule.
Generated SV binds remain enabled with Verilator assertions.

## Qualified directed goals

`rvw cov probe-goals` checks passing C1, complete C2, matching ELF and RTL
hashes, full per-cycle event accounting and a complete strict Spike match.
These results qualify the sampled project-owned wiring. They do not prove
whole-core coverage or grant C4 acceptance.

| Program | Cycles | Retirements | Qualified observations |
|---|---:|---:|---|
| precise-3, IRQ asserted at cycle 32 | 132 | 48 | One software interrupt at cycle 52 with all eight ROB entries occupied. |
| protection-speculative | 165 | 80 | One issued wrong-path load fault followed by control recovery within 40 cycles. One later load fault and one store fault commit in U-mode. |
| flush-chain | 307 | 112 | Two loads forward bytes while an older resolved branch awaits recovery. Both are followed by recovery within eight cycles. Twelve recovery gaps are between two and eight cycles. |

The forwarding byte mask is 15 for both observed events. The wrong-path fault
plan binds the exact load PC before the recovered label. A later committed
fault cannot satisfy that bin. Both sequence reports have zero pending states.

Consecutive-cycle recovery has zero hits and stays an open bin. Recovery
empties the ROB, so the normal pipeline must refill before another head can
redirect. No formal unreachable exclusion was applied. Other ROB capacities,
IRQ sources at full occupancy, byte masks, age combinations and privilege
transitions remain separate goals.

The original cycle-1000 precise-interrupt run enters with seven ROB entries.
It did not meet the full-ROB goal. The added cycle-32 schedule fills that gap.

## Tool fix

The protection trace contains 83 instruction records and 80 retirements.
The first probe qualification refused this complete strict match because it
compared the former count with C1 instret. [PR #1310](https://github.com/riscPrint/risc-v-workstation/pull/1310)
adds the generic nontrapping count. The corrected qualifier accepts the trace.
This change does not waive a mismatch, mask a field or add synchronization.

## Reproduce

Build the coverage prerequisites and manifest first. Then use fresh output paths:

```sh
nice -n 10 "$RVW_HOME/rvw/.venv/bin/python" rvw/check-probes.py
```

Run from the core project. Set RVW_SBT_LOCK=sbt-ooomini2 and use a private
RVW_OOO_LOCK. The script runs the fixed suites with probes, adds the cycle-32
schedule and qualifies three plans. It requires every positive bin and sequence
to hit. It reports the consecutive-cycle hole without treating it as a pass.
Raw plans, observations and reports stay under rvw/out. Probe-only runs have a
different instrumented RTL identity from the earlier coverage snapshot.
