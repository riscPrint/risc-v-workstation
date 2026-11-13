# Real multiplier product check

```sh
rvw/.venv/bin/python examples/vexriscv/formal/mul-smoke.py \
  --rtl /path/to/VexTop.v --out /path/to/new-run --width 32 --timeout 120
```

This example reads a supplied VexTop export. It locates the real
`MulSimplePlugin` product cell at `_zz_memory_MUL_1`. It copies that cell and its
operand bit connections into a separate module. It checks the expected 33-bit
operand interface and repeated sign-extension wiring before extraction.
The wrapper sets the operand sign bits to zero and observes the low result bits.
No multiplier logic is replaced with a new implementation.

The reference uses `models/mul32.c` and `models/riscv_m.h`. The wrapper masks the
reference to the observed result width. `--width 8` or `16` restricts both operands
to that many symbolic low bits. It sets their upper bits to zero. The result
comparison also uses only that many low bits. These restrictions are part of the
experiment. They are not full-width proofs.

The runner uses the private `vex-equiv` lock and `nice -n 10`. It retains the
supplied RTL, mapped JSON, selected cell, generated Verilog, reference C, native
logs and result. The source RTL hash binds the experiment to its supplied export.
The runner does not elaborate the core or certify its source revision.

## Recorded run, 2026-11-13

The initial hierarchical run exposed a generic frontend bug: Yosys `$scopeinfo`
metadata reached the arithmetic translator. The datapath JSON exporter now uses
`write_json -noscopeinfo`. A native nested-module regression passes.

After that fix, the 32-bit product check timed out in CBMC at 120 seconds.
It is inconclusive. The eight-bit operand and low-eight-bit result projection
proved. It checks 65,536 input pairs symbolically. See `mul-results.json` for the
exact input hash and scope. No full-width arithmetic result closed.

## Remaining work

This is an extracted product-cell check. It does not check instruction decode,
signed high products, pipeline stalls, writeback, divider transactions, VexiiRiscv
or an FPU against SoftFloat. The core's undriven CSR signals remain present in the
captured source. The extraction removes those unrelated cones. It cannot certify
the original core.
