# Real multiplier arithmetic helpers

`mul-unit.py` uses the committed `MulSpliter` and `AdderAggregator` definitions
from VexiiRiscv's `misc/Utils.scala`. It applies the default `MulPlugin`
arithmetic settings: 33-bit signed operand encodings, 17-bit partial products,
and sum steps `(44,8)` and `(1000,1000)`. The generated component joins these
arithmetic steps without pipeline registers. It uses the original helper
functions. It does not replace them with a direct multiply expression.

The adapter supplies the signed or unsigned extension required by MUL, MULH,
MULHU or MULHSU. It selects the correct 32 result bits. Source and component
hashes, the source revision, dependency version and RTL hash remain in the
ledger. Elaboration uses SpinalHDL 1.15.0.

```sh
rvw/.venv/bin/python examples/vexiiriscv/formal/mul-unit.py \
  --source /path/to/private/VexiiRiscv --out /path/to/new-run \
  --operand-bits 8 --timeout 180
```

The default operand width is 32. An explicit smaller width projects the inputs
in both the reference and the unit. Signed operands are sign extended.
Unsigned operands are zero extended. Eight bits give signed values -128..127
or unsigned values 0..255, as required by each operation. All 32 selected result
bits are compared. The projection does not truncate the result.

Native commands use `sbt-equiv` and `vex-equiv` with `nice -n 10`.
The runner returns zero only if all requested checks prove. A counterexample
returns one. Missing evidence returns three.

## Limits

This checks the actual helper arithmetic with the default multiplication and
sum settings. It does not check source-stage capture, inserted pipeline
registers, stalls, signedness decode, buffered high results, RVFI or ISA
integration. The released SpinalHDL build does not qualify the complete core
against its pinned development dependency. A projected input proof does not
establish full 32-bit operand behavior.

The native Python/C tests checked each projected M reference against independent
integer arithmetic for all 65,536 pairs per operation. These are reference-domain
tests. Read the separate native proof receipts for DUT outcomes.

## Recorded native results

All four operations proved for the stated eight-bit operand domains.
MUL took 108.077 seconds. MULH took 70.451 seconds. MULHU took 25.484 seconds.
MULHSU took 28.148 seconds. Source revision was
`9f70315deb3390b283995c5b8f1bd38215ecf52b`.
These are four restricted-domain proofs of the generated helper arithmetic.
They are not full-width or pipeline proofs.
See `default-unit-results.json` for the exact source and RTL hashes.
