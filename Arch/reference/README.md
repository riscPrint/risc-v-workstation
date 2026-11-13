# Approximate reference descriptions

These `rvw.arch-core/1` descriptions are starting points for RISC-V timing
experiments. They are not faithful models of the named commercial cores.
They accept RISC-V C2 traces, not x86 or Arm binaries. No IPC comparison with
those products is valid. All files pass the static shared description checker.
No gem5, RTL or hardware timing validation is included.

## Public anchors and assumptions

`zen5-like.json`: eight-wide integer rename and six integer ALUs follow
[AMD, Next Generation Zen 5 Core, Hot Chips 2024, slides 4 and 5](https://hc2024.hotchips.org/assets/program/conference/day2/24_HC2024.AMD.Cohen.Subramony.final.pdf).
The integer physical register count is 240. The 448-entry window is an
approximate design point, not a reproduced retire implementation. Queue sizes,
issue width, fetch queue, stage delays, latencies and branch cost are assumptions.
The two decode paths are collapsed into one width of eight. SMT, x86 decode,
vector execution and the real predictor are absent.

`m1-like.json`: the eight-wide pipeline and six integer ALUs follow
[Dougall Johnson's measured Firestorm overview](https://dougallj.github.io/applecpu/firestorm.html).
It describes several retirement structures. This file chooses 330 ROB entries
and 380 integer registers as approximate capacities. It does not add their
capacities together. Queue sizes, stage delays, timing, branch cost and cache
settings are assumptions. The model does not reproduce Arm decoding, coalesced
retirement, AMX or Firestorm's actual rename policy.

`boom-large.json` and `boom-mega.json`: shared dimensions copy the repository's
`examples/boom/arch/large.json` and `mega.json` snapshots. The `ooo` table adds
assumed fixed latencies and branch cost. The projection collapses partitioned
issue queues. These are not refreshed RTL extraction snapshots.

`vexriscv-class.json`: a serial integer baseline with one-wide rename and a
single ROB entry. This is an assumed small-core comparison point. It is not
an extracted VexRiscv configuration or a pipelined in-order model. VexRiscv's
configurable pipeline prevents a universal preset.

All predictor, cache, TLB, memory latency and FU settings inherited from the
repository template are assumptions unless named above. Sources do not validate
those settings. Check each field before using a description for a project.
Commercial names denote inspiration only. No model has an earned accuracy pass.

## Use

Copy a description into the core project. Set its `config` to the C2 header's
selected configuration. Run `rvw ooo DESCRIPTION TRACE --json`. The same
shared file is accepted by the existing gem5 adapter. Equal fields do not
establish timing parity between the two engines.
