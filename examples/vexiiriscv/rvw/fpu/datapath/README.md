# Real Vexii FP units

| Binding | Boundary |
|---|---|
| `FpuLaneHarness.scala` | Real lane decode, unpacker, add/mul/div/sqrt/convert paths, packer, writeback and FCSR flags |
| Entry | One instruction and stable operands enter the execution lane; register-file reads are replaced by the input operands |
| Excluded | Fetch, front decode, dispatch, register-file storage, privilege checks, flushes and overlapping transactions |
| Control | One transaction per reset; real operand-bank and source-enable metadata; CSR requests disabled outside the unit boundary |
| Output | Real FP or integer writeback data; actual stored FCSR flags after two settling clocks |
| `FpuSqrtHarness.scala` | Real mantissa sqrt component with a separate IEEE adapter for absolute normal inputs |

No core source is changed. The wrappers import the pinned core's classes.
They do not contain a replacement FP adder, multiplier, divider or converter.
The lane harness retains the real shared unpack and pack logic. Native tests
compare full result bits and all five exception flags with Berkeley SoftFloat.
Each case resets the unit and holds its inputs until completion.

| Native set | RV32 F | RV64 D and S/D conversions |
|---|---:|---:|
| Class boundaries plus seeded random bits | 57,200 matches | 91,520 matches |
| Operations | 10 | 16 |
| Rounding modes | 5 | 5 |
| Additional cases from Spike plans | 700 matches | 1,120 matches |
| Missing completion or mismatch | 0 | 0 |

Operations are add, sub, mul, FMA, div, sqrt and signed/unsigned W conversions.
RV64 adds signed/unsigned L conversions and S/D format conversions. Each
operation has 144 boundary cases and 1,000 raw-bit cases at each RM. Integer
sources also use integer boundaries. The seed is 1. FMA does not enumerate
every operand triple. Spike plans come from the self-checking generator.
The runner also checks their expected bits and flags against SoftFloat.
`testfloat_gen` was not installed. Spike supplies the extra saved vectors.

| RNE proof, 60-second limit | RV32 | RV64 | Completion bound |
|---|---|---|---|
| Add | A zero, NaN and infinity close in 48.2-50.4 s; other cases time out | All selected cases time out | 23 clocks |
| Mul | All selected cases time out | All selected cases time out | 23 clocks |
| Div | All selected cases time out | All selected cases time out | 50 / 80 clocks |
| Sqrt | A zero, NaN and infinity close in 53.3-53.9 s; other cases time out | All selected cases time out | 46 / 75 clocks |
| FP to signed W | All inputs close in 12.2 s; all selected case splits also close | All inputs close in 22.1 s; all selected case splits also close | 14 clocks |
| Signed W to FP | All inputs close in 13.8 s | All inputs close in 25.2 s | 20 clocks |

| Unrestricted signed W conversion proofs, all five RMs | RV32 | RV64 |
|---|---|---|
| FP to W | 5 proofs, 12.1-12.5 s each | 5 proofs, 21.4-22.6 s each |
| W to FP | 5 proofs, 13.8-14.3 s each | 5 proofs, 25.2-26.3 s each |

These 20 unrestricted proofs cover the five legal rounding modes for the
selected signed W variants. The lane matrix has 36 closed obligations and
42 timeouts across 78 attempts. Case splits are included in those counts.

Selected FP cases are all, normal, zero, subnormal, NaN and infinity on A.
B and C remain unconstrained. Integer-source conversion uses all inputs.
A closed case is not a whole-operation proof. Only the unrestricted `all`
result closes the selected operation and RM. The backend checks result bits,
flags, definedness and completion. It leaves timed-out cases inconclusive.
Unsigned/L and S/D conversion proofs were not run. Their evidence is native
vectors. No whole-core proof is implied.

The completion limits are the largest observed native latency plus four
clocks. The proof asserts completion within that limit. It does not assume
completion. Runs used nice 15. The RV32 lane batch started at load averages
12.37, 9.70 and 8.97. The RV64 batch started at 8.82, 8.77 and 9.61. These times describe this loaded machine.

The separate mantissa sqrt wrapper matched 50,000 positive normal vectors
per width across five RM values. Its normal-case proofs at both widths and
all five RMs timed out at 60 seconds. It does not check the core's IEEE
unpacker or packer. The lane results above cover those parts.

## Regenerate

Use the private core at `9b63f47fe559dbba7874af9196746412fa1294c1` and
SpinalHDL at `de72faf6062206a89b445e5cc07e32ed982712c8`. Build a normal
FP C1 run first, as described in the parent README. The emitter reuses that
completed classpath. It checks its bytecode identity and writes its own classes
and RTL outside the repository. It does not rebuild a CPU simulation model.
Clone Berkeley SoftFloat at `07ebd29db0cfb55723a79fbbffe99103ef38e305` into
`$SOFTFLOAT`. Keep it outside the core copy and the workstation checkout.

```sh
unit=examples/vexiiriscv/rvw/fpu/datapath
scripts/with-lock.sh sbt-fpu nice -n 15 rvw/.venv/bin/python "$unit/emit.py" \
  --kind lane --width 32 \
  --classpath-cache "$RISCVSIM_WORK/vexii-classpath.json" \
  --out "$RVW_FPU_RUN_ROOT/unit32"
scripts/with-lock.sh vex-fpu nice -n 15 rvw/.venv/bin/python "$unit/lane_unit.py" \
  --width 32 --rtl "$RVW_FPU_RUN_ROOT/unit32/rtl/VexiiRiscv.v" \
  --softfloat "$SOFTFLOAT" --out "$RVW_FPU_RUN_ROOT/unit32-check" \
  --spike-plans "$RVW_FPU_RUN_ROOT/directed32/oracle"
```

Use width 64 for the RV64 unit. Supply both RV64 S and D oracle directories
with `--spike-plans` when they are separate. Reuse the one native unit model
for all operations at that width. The runner stops on the first mismatch.
Its `vectors.jsonl` records counts and the largest completion latency.

The following loop regenerates the RNE case-split matrix. Use the matching
width, RTL and completion limit from the table above.

```sh
for op in add mul div sqrt to-int from-int; do
  case "$op" in
    add|mul) limit=23 ;;
    div) limit=50 ;;
    sqrt) limit=46 ;;
    to-int) limit=14 ;;
    from-int) limit=20 ;;
  esac
  nice -n 15 rvw/.venv/bin/python "$unit/lane_formal.py" \
    --width 32 --rtl "$RVW_FPU_RUN_ROOT/unit32/rtl/VexiiRiscv.v" \
    --softfloat "$SOFTFLOAT" --out "$RVW_FPU_RUN_ROOT/proof32-$op" \
    --operations "$op" --max-latency "$limit" --timeout 60
 done
```

`lane_formal.py` fixes the operation and RM before Yosys removes unused
logic. It writes an explicit port binding and used legacy `formal datapath` against the existing pinned SoftFloat dependency runner. Use `--rounding 1`
through `4` and `--cases all` for conversion RM checks. Keep full result JSON,
solver logs, extracted RTL and builds outside the repository.

For the smaller sqrt component, emit with `--kind sqrt`. Run `sqrt_unit.py`
with its `FpuSqrtHarness.v`, width, SoftFloat tree and a fresh output path.
Add `--formal --timeout 60` to repeat its five normal-case RM attempts.
