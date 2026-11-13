# MEPC decisions for six ACT4 cases

The declared profile is RV32IM with Zicsr and no C extension. These
decisions use the saved native observations. A fresh six-program minimal campaign reports six C1 failures and six
strict Spike mismatches with no masks or synchronization. See
`mepc-review.json` for ELF hashes, C2 hashes and first differences.
The original six full ACT4 cases were not rerun. The table records first differences, not complete Spike matches.

| ACT4 case | First read: RTL | First read: Spike | Minimal MEPC write | Decision |
|---|---|---|---:|---|
| Zicsr-csrrc-00 | `0xfaf331f` | `0xfaf331c` | 3 | Core CSR readback difference |
| Zicsr-csrrci-00 | `0x262b870e` | `0x262b870c` | 2 | Core CSR readback difference |
| Zicsr-csrrs-00 | `0xd5991566` | `0xd5991564` | 2 | Core CSR readback difference |
| Zicsr-csrrsi-00 | `0x8b4b5cff` | `0x8b4b5cfc` | 3 | Core CSR readback difference |
| Zicsr-csrrw-00 | `0x2f76bb91` | `0x2f76bb90` | 1 | Core CSR readback difference |
| Zicsr-csrrwi-00 | `0xcb07a0c9` | `0xcb07a0c8` | 1 | Core CSR readback difference |

For each row, build `mepc-case.S` with `CASE=0..5` in table order.
Each program uses its case's CSR read instruction. `mepc-alignment.S`
also accepts the listed `MEPC_VALUE` as a common control.
The program writes that value to MEPC, reads MEPC, and checks bits 1:0.
For this profile, Spike reads zero for values 1, 2 and 3. The saved RTL
controls fail for all three values. The six cases exercise different CSR
instructions but expose the same alignment rule.

The [MEPC rule](https://docs.riscv.org/reference/isa/priv/machine.html) requires
bit 0 to read zero in every configuration. Bit 1 must also read zero when
IALIGN=32. With C enabled and IALIGN=16, bit 1 can hold a value. A core that
can switch IALIGN must mask bit 1 on reads when IALIGN=32. This example
does not declare C. Retaining bit 1 is not an allowed choice here.

Decision for all six: retain failures and record one shared MEPC finding.
Do not add a CSR mask, synchronization, or an ACT4 exception. The shared
cosim platform JSON already selects the uncompressed ISA. It needs no
new setting to describe these six failures.

## Comparison with other tools

[VEX-PC-CHAIN-001](../../FINDINGS.md#vex-pc-chain-001) independently writes
`0x80000019`. RTL reads `0x80000019`; Spike reads `0x80000018`. Both next
retire at `0x80000018`. This agrees with the ACT4 bit-0 readback finding.
It does not establish that MRET executes at an odd address.

[VEX-MRET-MPP-001](../../FINDINGS.md#vex-mret-mpp-001) is independent.
MRET clears MPP to 0 while only M is supported. The required least
privileged supported mode is M, so MPP must become 3. The legal option
to hard-wire MPP to M does not permit the observed zero.

[VEX-MTVAL-IRQ-001](../../findings/interrupt-mtval/README.md) covers three
separate inputs: MSIP, MTIP and MEIP. Each minimal program preloads
`mtval=0x55`. RTL retains it on interrupt entry; Spike clears it to zero.
The interrupt rule requires zero. These are separate from the MEPC read
differences. None is a legal platform choice. No core source was changed.
