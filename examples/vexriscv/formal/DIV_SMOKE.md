# Real divider plugin transactions

```sh
rvw/.venv/bin/python examples/vexriscv/formal/div-smoke.py \
  --rtl /path/to/VexTop.v --out /path/to/new-run --divisor zero --timeout 90
# Unrestricted divisor:
rvw/.venv/bin/python examples/vexriscv/formal/div-smoke.py \
  --rtl /path/to/VexTop.v --out /path/to/new-full-run --divisor full --timeout 90
```

This example extracts the real `DivPlugin` cone from a supplied VexTop export.
It cuts operand, opcode, stage-valid and stage-stall boundaries. Cuts apply to
all aliases of each selected bit. It keeps the full backward state cone of the
plugin result and completion flag. It does not replace the divide algorithm.
The original RTL hash and boundary widths remain in `summary.json`.

The transaction adapter holds operands stable. It supplies one fixed opcode and
its signedness controls. It starts the memory stage after the start pulse and
stalls that stage until completion. Reset includes an idle clock, which loads
operand state and clears completion. The check requires the first completion
within 64 clocks. Result comparison uses the independent RISC-V M model.
Native commands use `vex-equiv` and `nice -n 10`. Four operations run in sequence.

## Recorded run, 2026-11-13

DIV, DIVU, REM and REMU proved for every 32-bit dividend with divisor zero.
The fixed divisor applies to both the actual plugin and the reference model.
These are boundary-case proofs, not sampled dividends. Each completed within
90 seconds. All four unrestricted-divisor runs timed out in CBMC at 90 seconds.
See `div-results.json`. No unrestricted divide or remainder result closed.

## Limits

Stage controls and opcode are supplied by the adapter. Decode, pipeline hazards,
writeback, core reset sequencing, multi-transaction behavior and ISA integration
are not checked. The captured core export was not freshly elaborated or certified
against its source revision. Its unrelated undriven CSR signals remain a separate
whole-core fault. The extracted cone does not include those signals. No constant
was added to bypass a fault in the selected arithmetic cone.

Script completion means that the run ledger was written. It does not mean that
all operation checks proved.

## Fresh continuation check

The fresh DIVU zero-divisor run timed out at 90 seconds while other unit
proofs ran. An isolated retry with a 180-second limit proved in 98.286 seconds.
Both attempts use the same captured core RTL and the 64-clock completion
obligation. See `SpinalChecks/c2rtl/resume-results.json`. The full-divisor case
remains unproved.
