# Machine interrupt checks

The core samples MSIP, MTIP and MEIP at a completed ROB head. It takes the
interrupt before that head commits. It restores the committed rename map,
flushes the ROB and multiply/divide unit, and redirects to `mtvec`.
No store or destination register commits on the interrupt edge.
`mepc` is the discarded head PC. `mcause` has the interrupt bit and source
number. `mtval` is zero. Priority is MEIP, MSIP, then MTIP.
Direct and vectored `mtvec` are supported. WFI may return early as permitted
by the privileged specification. It does not stop the simulation clock.

Run from the workstation checkout with RISC-V GCC and native tools on PATH:

```sh
export RVW_HOME="$PWD"
export RVW_SBT_LOCK=sbt-ooomini2
export RVW_OOO_LOCK=ooo-mini-ooomini2
rvw/.venv/bin/rvw --project examples/ooo-mini regress plan \
  --features examples/ooo-mini/rvw/features.json --json
nice -n 10 python3 examples/ooo-mini/rvw/check-interrupts.py
```

The script requires a fresh output directory. It builds the six generated
scheduled-WFI cases. The enabled cases check trap cause and exception PC.
The masked cases check pending state without trap entry.
`interrupt-precise.S` also checks zero `mtval` after a nonzero value, MIE/MPIE,
return from the handler, and division with store-to-load forwarding.
Compile it with `-DIRQ_CAUSE=0x80000003`, `0x80000007` or `0x8000000b` and
use the corresponding schedule. Raw C1/C2 and check reports stay in `rvw/out`.

C2 records pin changes and trap events. The first handler
instruction has `intr=true`. No interrupt is represented as a retired instruction.
CLINT and PLIC plugin routing is not mapped in this increment. Device families
are not declared as supported. The PLIC external-interrupt declaration is not emitted for scheduled pins.
Live lockstep comparison remains to be run.

## Measured increment

Seed 17, default eight-entry core, nine self-checking RV32IM programs:

| Family | RTL pass/run | Cycles per case | Retirements per case | Strict Spike match | Native monitor firings |
|---|---:|---:|---:|---:|---:|
| Directed precise interrupt, three sources | 3/3 | 1110 | 298 | 3/3, zero synchronization | 0, 20 monitors |
| Generated WFI, MIE set | 3/3 | 1033 | 819 to 851 | 3/3, zero synchronization | 0, 20 monitors |
| Generated WFI, MIE clear | 3/3 | 1028 to 1033 | 813 to 850 | 0/3: asserted `mip` pin reads differ | 0, 20 monitors |

Each masked case also matches with one explicit IRQ synchronization.
The masked cases expose the existing pin-read reference limit. Spike has no
scheduled input during these CSR reads. This is separate from interrupt trap
injection, which the six strict traces exercise. The default generated SV binds
also ran with Verilator assertions enabled. None fired. These results do not
cover CLINT/PLIC plugins, live lockstep, vectored delivery, or every ROB state.
