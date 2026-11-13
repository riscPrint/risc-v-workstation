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
