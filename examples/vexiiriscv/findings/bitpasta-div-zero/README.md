# Bitpasta IPC division by zero

Confirmed on the pinned VexiiRiscv core through Verilator and Spike.
Select `rv32im_bitpasta_ipc`, equivalent to upstream
`--div-impl bitpasta --div-ipc`. This instantiates `DivRadix2` with
`lowArea=false`. Default and bitpasta area configurations pass the four
measured rv32um programs.

`minimal.S` divides unsigned 1 by zero. The required quotient is
`0xffffffff`. The IPC core returns `0x808080ab` and reports tohost 3.
Link with `../../rvw/programs/link.ld` from this directory.

The rv32um DIV and DIVU programs fail test 8 for dividend `0x80000000`
and divisor zero. Spike confirms the wrong register writeback. Both
remainder programs match Spike. Signed overflow returns quotient
`0x80000000` and remainder zero as required.

See [the diagnosis and reproduction steps](../../formal/DIV_UNIT.md#core-diagnosis-2026-11-13)
and [compact receipts](../../formal/div-core-results.json).
The core source is unchanged. This finding is not a full arithmetic proof.
