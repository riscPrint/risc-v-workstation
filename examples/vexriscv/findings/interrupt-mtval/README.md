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
`tval` expected `0x0`, actual `0x55` at the interrupt trap. Disposition is open.
The workstation does not change the core.
