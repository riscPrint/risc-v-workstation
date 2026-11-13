# Private check controls

Use a private checkout at the pinned NaxRiscv revision. Apply `planted-bugs.patch`
there. Keep `RVW_NAX_LOCK=nax-dbg` and `RVW_NAX_SBT_LOCK=sbt-dbg`. Do not apply
the patch to the shared core checkout. With no `RVW_NAX_PLANT`, the patch keeps
the original behavior.

Generate checks from `rvw/micro-checks.json`. Set `RVW_NAX_CHECKS` to the
result's queue-monitor directory. Build `forward-control.S` with the example's
`programs/link.ld`, `-march=rv32ima_zicsr_zifencei -mabi=ilp32 -nostdlib` and
`-nostartfiles`. The other two controls use the ISA `rv32ui-p-add` ELF.

Run each program through `rvw/run.sh run --seed 1 --mem-latency 0
--rvfi-trace --max-cycles 20000`. Use a new output directory for each run.
First run without a plant. Then select one mutation:

| Value of `RVW_NAX_PLANT` | Program | Target rule |
|---|---|---|
| `rob` | `rv32ui-p-add` | `rob_conservation` |
| `freelist` | `rv32ui-p-add` | `int_freelist_ghost` |
| `forward` | `forward-control` | `sq_forward_youngest` |

Check the target rule in `checks-run.json`. A failing C1 status alone does not
show that the target rule caught the bug. The measurements use seed 1. A clean
unseeded directed run fired other rules. Its cause remains unresolved.
See `check-results.json` for successful controls and failed attempts.

## ISA and fault controls

`isa-negative.patch` changes integer ALU writeback only when
`RVW_NAX_PLANT=alu`. Apply it to the private pinned core. Run `rv32ui-p-add`
with seed 1. Keep checks disabled for this co-simulation control. The expected
first mismatch is `li ra, 0` at PC `0x80000050`, C2 order 1. The mutant writes
1. Spike expects 0. The simulation can also end on a core assertion. The
co-simulation comparison must show the earlier architectural mismatch.

`seeded-adapter.sh` fixes the native seed at 1 and refill wait at zero. Use it
for the saved `fault-plan.json`. That plan flips one bit in each of the ROB
allocation, commit and free pointers at cycle 150. It samples three of 21
bit/cycle positions. It is not a safety or diagnostic-coverage qualification.

```sh
nice -n 15 rvw fault run --plan rvw/plants/fault-plan.json --adapter ./rvw/plants/seeded-adapter.sh --elf rvw/out/isa/rv32ui-p-add --out rvw/out/fault-controls --jobs 1 --max-cycles 20000 --timeout 180
```

Unset `RVW_NAX_PLANT` and `RVW_NAX_CHECKS` for the fault run. Use private core
and sbt locks. `negative-control.json` and `fault-results.json` keep the
measured evidence. A `not_injected` outcome is not a successful injection.
