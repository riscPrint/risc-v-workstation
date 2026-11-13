# Finding: interrupt traps keep the old mtval

Core: VexRiscv `baf7dc82f855eddaf5b0a20a6802c526f127e38a`, `rv32im` example
configuration. Found on 2026-11-13 by the generated scheduled-WFI suite.

The privileged ISA (Machine Trap Value Register) sets `mtval` to zero for
traps other than the listed exceptions. VexRiscv `CsrPlugin` writes `mtval`
only `when(hadException)`. An interrupt trap therefore keeps the previous
value. After reset that value is the unreset register content.

`mtval.S` writes 0x55 to `mtval`, waits for a machine timer interrupt and
reads `mtval` in the handler. Build it with `link.ld` and run it with an MTIP
schedule:

```sh
riscv64-unknown-elf-gcc -march=rv32im_zicsr -mabi=ilp32 -nostdlib -nostartfiles \
  -T link.ld mtval.S -o mtval.elf
rvw/run.sh run --elf mtval.elf --out out --rvfi-trace --irq-schedule 1:0x0,200:0x80 --json
rvw cosim check --core reference --platform rvw/platform.json --elf mtval.elf \
  --trace out/rvfi.jsonl --strict-sync counter,mmio,irq --json
```

Measured: C1 `fail` with `tohost = 0x3`. The Spike comparison reports
`tval` expected `0x0`, actual `0x55` at the interrupt trap. Disposition: core defect. This is not a legal M-only implementation choice.
The workstation does not change the core.


## Three interrupt decisions

Fresh minimal RTL runs on 2026-11-13 give the same defect for all three pins.
Each program writes `mtval=0x55` before enabling its interrupt. Each handler
reads `mtval` and reports failure if it is nonzero. The programs differ only
in the enabled input and expected `mcause`.

| Input | Program | Schedule | RTL mtval | Spike mtval | Decision |
|---|---|---|---|---|---|
| MSIP | `msip.S` | `1:0x0,200:0x8` | `0x55` | `0` | Core defect |
| MTIP | `mtval.S` | `1:0x0,200:0x80` | `0x55` | `0` | Core defect |
| MEIP | `meip.S` | `1:0x0,200:0x800` | `0x55` | `0` | Core defect |

Build each file with the command above and use its schedule. Each RTL run
reports C1 fail with `tohost=3`. The Spike comparison reports only the trap
`tval` difference at interrupt entry. [The record](triage.json) retains the
ELF, RTL and trace hashes, trap values and comparison result for each input.
The comparison permits one unspecified `mscratch` reset synchronization.
Counter, MMIO and IRQ synchronizations are disabled. Use
`--strict-sync counter,mmio,irq` to reproduce this comparison. A fully strict
comparison stops earlier at the unspecified scratch reset value.

The rule is in Machine-Level ISA 1.13,
[Machine Trap Value Register](https://docs.riscv.org/reference/isa/v20260120/priv/machine.html#_machine_trap_value_mtval_register):
traps outside the listed exception cases set `mtval` to zero. Interrupts are
outside those cases. The rule has no M-only exception. An implementation may
make `mtval` read-only zero. This core accepts the software write, then retains
that nonzero value across an interrupt. It therefore violates the rule.
No cosim platform setting is added to permit this defect. The existing M-only
privilege and absent-PMP settings remain separate legal platform choices.
The workstation does not change the core.
