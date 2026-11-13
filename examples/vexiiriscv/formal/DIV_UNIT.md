# Real VexiiRiscv divider unit

`div-unit.py` copies the committed `DivRadix.scala` and `DivRadix2.scala`
component definitions from a private source checkout. It removes simulation
entry points only. It exports the real 32-bit `DivRadix2` with
`lowArea=false` against SpinalHDL 1.15.0. Source and component hashes remain in
the ledger. This is the optional `bitpasta` implementation in VexiiRiscv's
`Param.scala`. It is not the default `DivRadix` implementation.

```sh
rvw/.venv/bin/python examples/vexiiriscv/formal/div-unit.py \
  --source /path/to/private/VexiiRiscv --out /path/to/new-unit-run \
  --divisor zero --operations divu --max-latency 12 --zero-smoke --timeout 180
# Restricted input projection with full 32-bit results:
rvw/.venv/bin/python examples/vexiiriscv/formal/div-unit.py \
  --source /path/to/private/VexiiRiscv --out /path/to/new-projection \
  --operand-bits 8 --timeout 180
```

The transaction adapter holds operands stable, applies synchronous reset and
starts one request. It compares the first completion against the RISC-V M model.
The declared bound is a completion obligation. It is not a fixed latency
assumption. Shift skipping can change latency with operand values.
The default bound is 40 clocks. The shorter zero-divisor check used 12.

The optional operand projection masks both reference operands and both unit
operands. It still compares every 32-bit result bit. A zero divisor applies to
both the unit and the reference. Decode, signed conversion, pipeline stalls,
writeback, multi-transaction behavior and whole-core integration are outside
this check. The exporter uses the released SpinalHDL dependency. It does not
qualify the complete core build against its pinned development dependency.

The runner uses `sbt-equiv` and `vex-equiv` locks. Native commands use
`nice -n 10`. It returns zero only when every requested proof closes.
A counterexample or smoke mismatch returns one. Missing evidence returns three.

## Recorded native results

Source revision: `3cff1cc2411ca97e6ee9ef64414ef274d30371e1`.
RTL SHA-256: `85e6dbad789d81ea6763afea55ed5878759f4e29ad9ef147f3fcf8e5dc66005f`.

The initial 40-clock DIVU and REMU zero-divisor checks each timed out at
180 seconds. They remain inconclusive.

The 12-clock DIVU zero-divisor check found a result counterexample in
82.94 seconds. Definedness proved. Completion-bound assertions succeeded.
The failing assertion was `datapath result`. The concrete formal dividend was
`2147707387`. The physical divisor and reference divisor were both zero.
The unused external divisor input stayed symbolic.

An independent Icarus sample with `a=1` and `b=0` returned quotient
`0x808080ab`. The M model requires `0xffffffff`. Completion occurred eight
clocks after the request sample. The simulation preserved the exported unit
assertions. No divider source was changed.

This is a confirmed mismatch for the re-elaborated unit and this interface.
A full core ISA reproduction was NOT RUN. No core source was patched.
Signed divide, unrestricted nonzero divisors and the VexiiRiscv multiplier remain
open. No divider arithmetic pass is claimed.

See `div-unit-results.json` for compact native receipts. The full 173 MB CBMC
counterexample remains in the private run directory. It is not committed.
The ledger records its hash.

The additional unrestricted binary32 HardFloat add retry also timed out at
180 seconds. It remains inconclusive. It does not change the earlier FPU ledger.

## Pinned example recheck

The complete runner was also run on the example pin
`9f70315deb3390b283995c5b8f1bd38215ecf52b`. It exported byte-identical RTL.
Icarus reproduced the same `1 / 0` mismatch. The 12-clock M-model check returned
a counterexample in 105.869 seconds. The runner returned exit one.
The source class is therefore also present at the example pin.
Full-core behavior and the pinned development SpinalHDL build remain unchecked.

## Default divider implementation

Use `--implementation DivRadix` to export the default radix-two arithmetic unit.
Its normalization can change the response latency. The same stable-operand,
first-completion contract applies. Use the default 40-clock bound.

On the example pin, DIVU and REMU both proved for every 32-bit dividend with
divisor zero. Times were 59.056 and 45.531 seconds. Icarus returned
`0xffffffff` for the separate `1 / 0` sample. These results apply to
`DivRadix`. They do not clear the `DivRadix2` mismatch above.
Nonzero unrestricted divisors and signed operations remain open.

## Core diagnosis, 2026-11-13

Decision: this is a real ISA difference in the optional IPC configuration.
It is not a unit harness error. Select `--div-impl bitpasta --div-ipc` in
upstream `ParamSimple`, or `rv32im_bitpasta_ipc` in this example.
`DivPlugin` instantiates `DivRadix2(32, lowArea=false)`. The example pin is
`9f70315deb3390b283995c5b8f1bd38215ecf52b`.

The core supplies unnormalized unsigned magnitudes. It holds operands while
execution is frozen. It consumes the response with `flush`, with response
`ready` low. Those differences from the standalone consumer do not repair
the first quotient. Signed conversion in `DivPlugin` explicitly prevents
negation of a division-by-zero quotient.

The skip logic uses shifts of 1, 2 or 8. On a zero denominator it skips
quotient positions that must contain ones. The quotient update appends one
`doSub` bit after each shift. That skip is invalid for division by zero.
No core source was changed.

| Core instruction | Dividend | Divisor | RTL result | M result |
| --- | --- | --- | --- | --- |
| DIV | `0x80000000` | `0` | `0x808080ab` | `0xffffffff` |
| DIVU | `0x80000000` | `0` | `0x808080ab` | `0xffffffff` |
| REM | `0x80000000` | `0` | `0x80000000` | `0x80000000` |
| REMU | `0x80000000` | `0` | `0x80000000` | `0x80000000` |
| DIV, signed overflow | `0x80000000` | `0xffffffff` | `0x80000000` | `0x80000000` |
| REM, signed overflow | `0x80000000` | `0xffffffff` | `0` | `0` |

The native Verilator core run used the pinned development SpinalHDL source.
It ran external riscv-tests revision
`d7e86f701b929b5d801f8cda1a4871ab05f452bb`, `rv32um` programs `div`,
`divu`, `rem` and `remu`. DIV and DIVU failed at test 8. The remainder
programs passed. The earlier independent Icarus unit result for `1 / 0`
remains `0x808080ab`; the required quotient is `0xffffffff`.
These are simulation results, not unrestricted arithmetic proofs.

`../findings/bitpasta-div-zero/minimal.S` is the minimal self-checking program. Link it with the example
`rvw/programs/link.ld`. It reports tohost 3 on the faulty quotient.
Use `div-core.py --tests /path/to/riscv-tests --out /path/to/new-run` to
build all four upstream tests, run the optional core and compare its commits
with Spike. Set `VEXIIRISCV` to the private pinned core first. The runner
limits each native step to two minutes. Build the current Spike shim with
`Cosim/build.sh` before the comparison. `--config rv32im` selects the default
control. `--config rv32im_bitpasta` selects the optional area control.
The unit exporter also accepts `--low-area` for that control.

Spike shim 8 confirmed the first difference at PC `0x80000228` for DIV
and `0x8000022c` for DIVU. Both differences are `rd_wdata`: expected
`0xffffffff`, observed `0x808080ab`. The REM and REMU traces match Spike.
See `div-core-results.json` for compact receipts and trace hashes.

Control runs: all four programs passed on `rv32im` and
`rv32im_bitpasta`. The fault requires the IPC skip configuration in this
measurement. The minimal `../findings/bitpasta-div-zero/minimal.S` also failed on the IPC core with
tohost 3. These control traces were not compared with Spike.
