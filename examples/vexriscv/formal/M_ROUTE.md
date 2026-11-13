# Multiplier and divider route

The adapters accept `--top VexRiscv` for the measured FormalMTop export.
They retain the source digest before the top is renamed for extraction.
They use `vex-conn` and `nice -n 15`. Each operation runs in sequence.

The product adapter selects MUL, MULH, MULHSU or MULHU. It supplies the
signedness bit of each 33-bit input and observes the full selected RV32 result.
`--width 8` restricts each operand to eight meaningful bits. Signed operands
are sign extended. Unsigned operands are zero extended. The independent RV32
reference receives the same domain restriction. This is not an eight-bit core
or an unrestricted RV32 proof. Decode and pipeline control remain separate.

The divider adapter accepts `--operand-bits 8`. It keeps the full 32-bit
DivPlugin state cone and the 64-clock first-completion requirement. Only the
operand domain changes. It does not replace the divider with an eight-bit unit.
The fixed-opcode stage adapter and stable-operand contract remain in force.
The full-width timeouts in DIV_SMOKE.md and SAIL_M.md remain unresolved.

```sh
rvw/.venv/bin/python examples/vexriscv/formal/mul-smoke.py \
  --rtl BUILD/VexRiscv.v --top VexRiscv --operation mulh \
  --width 8 --timeout 60 --out OUT
rvw/.venv/bin/python examples/vexriscv/formal/div-smoke.py \
  --rtl BUILD/VexRiscv.v --top VexRiscv --operand-bits 8 \
  --timeout 30 --out OUT
scripts/with-lock.sh vex-conn nice -n 15 rvw/.venv/bin/python \
  examples/vexriscv/formal/uf_m.py --project SAIL_PROJECT \
  --timeout 45 --out OUT
```

`SAIL_PROJECT` is the generated project from `run_sail_m.py`. Its pinned Sail
MUL and MULHU instruction models remain intact. The UF runner captures upstream
unbounded instruction checkers. It replaces global typed multiplication terms
in both core and reference. Source assumptions remain part of the proof scope.
An abstract counterexample is inconclusive. It is not a core failure.

The measured UF captures contain different multiplication widths, including
128 and 64 bits. Each width uses a separate UF. Those UFs do not establish
the arithmetic relation between different widths. Both checks returned abstract
counterexamples. Arithmetic refinement is required before these checks can
close. No decode or retirement proof is claimed.

See `m-route-results.json` for the measured native attempts. No new unrestricted
RV32 arithmetic proof closed. The earlier low-eight-bit MUL and zero-divisor
proofs retain their original narrow scope. No result here replaces them.

## Native outcomes, 2026-11-13

| Operation | Operand domain | Outcome | Budget |
| --- | --- | --- | --- |
| MUL | unsigned 8-bit operands, full low RV32 result | inconclusive, timeout | 30 s |
| MULH | signed 8-bit operands, full high RV32 result | inconclusive, timeout | 60 s |
| MULHSU | signed/unsigned 8-bit operands, full high RV32 result | proved | 30 s |
| MULHU | unsigned 8-bit operands, full high RV32 result | proved | 30 s |
| DIV | signed 8-bit operands, 64-clock completion | inconclusive, isolated retry timed out | 30 s |
| DIVU | unsigned 8-bit operands, 64-clock completion | inconclusive, timeout | 30 s |
| REM | signed 8-bit operands, 64-clock completion | inconclusive, timeout | 30 s |
| REMU | unsigned 8-bit operands, 64-clock completion | inconclusive, timeout | 30 s |

The first DIV capture exhausted its budget in a private-lock queue. The
isolated retry reached CBMC and timed out. An early MUL capture also expired
in that queue. The table uses its later native retry. These queue failures
are not arithmetic counterexamples.
