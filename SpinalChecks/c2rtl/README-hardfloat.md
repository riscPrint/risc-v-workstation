# Native HardFloat checks

`hardfloat.py` exports real Berkeley HardFloat units and compares them with
Berkeley SoftFloat through `rvw formal datapath`. It supports binary16 and
binary32 add, multiply, fused multiply-add, divide, square root and signed
32-bit integer conversions. Every check compares result bits and exception flags.

## Sources

Keep both source trees outside the repository. Use the official
[HardFloat Release 1 archive](https://www.jhauser.us/arithmetic/HardFloat-1.zip).
Its SHA-256 is
`6b3757c9fbfa2230c6a2b84605e39372cb589dd7500e979c4f0b8ecc8a03b14b`.
The runner records every source file hash. Select the `RISCV` specialization.
Use [SoftFloat commit 07ebd29](https://github.com/ucb-bar/berkeley-softfloat-3/tree/07ebd29db0cfb55723a79fbbffe99103ef38e305).
The existing dependency helper rejects other SoftFloat revisions. Generated
reference C and each copied dependency tree remain in the native output.

```sh
rvw/.venv/bin/python SpinalChecks/c2rtl/hardfloat.py \
  --hardfloat /path/to/HardFloat-1 --softfloat /path/to/berkeley-softfloat-3 \
  --out /path/to/new-run --operations add,mul,fma,div,sqrt,to-int,from-int \
  --cases zero,nan --roundings 0,1,2,3,4 --max-latency 4 --timeout 90 --jobs 3
# Unrestricted binary16 addition:
rvw/.venv/bin/python SpinalChecks/c2rtl/hardfloat.py \
  --hardfloat /path/to/HardFloat-1 --softfloat /path/to/berkeley-softfloat-3 \
  --out /path/to/new-half-run --format 16 --operations add --cases all \
  --roundings 0,1,2,3,4 --timeout 90 --jobs 3
```

The runner starts at most three native jobs. Each uses `nice -n 10`. Each proof
has its own timeout and output tree. RTL export runs before proof jobs start.
`summary.json` records source hashes, format, operation, case, rounding, bounds
and verdicts. No export failure or missing result produces a proof status.

## Proof contract

Cases constrain only the first floating-point operand. Other operands stay free.
`from-int` always uses all signed 32-bit inputs. Binary16 integer conversions use
the existing explicit input/output width bindings. No operand bits are discarded
from a 32-bit integer conversion. Floating results use the RISC-V canonical NaN.
Tininess is detected after rounding. Flags include invalid and inexact conversion
results. HardFloat integer invalid/overflow indicators map to the RISC-V NV flag.

Divide and square root use one reset clock and one start pulse. Operands remain
stable until the first completion. `--max-latency` is a completion obligation,
not an assumption. Four clocks suffice for the recorded zero/NaN cases. Use a
larger bound for normal operands. The original 64-clock special-case runs timed
out while the four-clock obligations closed. No clock cycles are ignored after
the reset procedure.

The Boolean translator accepts rising-edge asynchronous-reset flops only when
their reset is the declared active-high public reset. It applies reset values
before combinational evaluation and clock capture. This models the transaction
samples. It does not model input changes between samples. Other reset and clock
sources remain refused. This is not a reset-domain crossing or physical proof.

## Evidence limits

See `hardfloat-results.json` for the native run ledger. A zero/NaN case result
does not cover normal, subnormal or infinity first operands. Unrestricted
conversion results have no floating-point class restriction. All-domain arithmetic
runs that time out remain inconclusive. Parameterized binary16 results do not
establish binary32 arithmetic. These are unit checks, not whole-FPU integration,
core, streaming, ISA or hardware proofs.

## Recorded run, 2026-11-13

The ledger contains 130 attempted proof runs. Of these, 85 closed. The other 45
were inconclusive. These are run receipts, not independent coverage scores.

- Binary32: add, multiply, FMA, divide, square root and float-to-int zero/NaN
  first-operand cases closed for all five rounding modes.
- Binary32: both signed 32-bit integer conversion directions closed with no
  operand-class restriction for all five rounding modes.
- Binary16: addition closed with unrestricted operands and all five rounding
  modes. Both signed 32-bit integer conversion directions also closed without
  input-class restrictions for all five rounding modes.
- Unrestricted binary32 add, multiply and FMA timed out under round-to-nearest.
  Unrestricted binary16 multiply and FMA also timed out under that mode.
- Early divide/square-root runs were refused for public asynchronous-reset
  flops. After translator support was added, 64-cycle runs timed out. The
  four-cycle zero/NaN completion obligations then closed.

Normal-operand divide and square root, full binary32 arithmetic and unrestricted
multiply/FMA remain open. No timeout or earlier refusal is counted as a proof.

Script completion means that the campaign ledger was written. It is not an
aggregate proof verdict. Read each native result status.

## Fresh continuation checks

The continuation run proved unrestricted binary16 addition and both signed
32-bit integer conversion directions under round-to-nearest. It used the
current translator and the pinned sources above. Times were 77.621, 5.928 and
9.206 seconds. See `resume-results.json`. These three fresh checks do not
replace the earlier 130-run ledger or extend its operation and rounding coverage.
