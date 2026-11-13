# FP verification on VexiiRiscv

| Input | Pin or setting |
|---|---|
| VexiiRiscv | `9b63f47fe559dbba7874af9196746412fa1294c1`, private copy, no tracked source changes |
| SpinalHDL | `de72faf6062206a89b445e5cc07e32ed982712c8` |
| ACT4 | `56d40ab301dba23dd3104c17bd969afbaaea1931`, private checkout |
| Berkeley SoftFloat | `07ebd29db0cfb55723a79fbbffe99103ef38e305` |
| Native corpus adapter | `3488f2d8666e515642c2213ba8e22052eaa35e1f` |
| Configurations | Extra `rv32imafc` and `rv64imafdc`; existing defaults unchanged |
| Platform | One hart, machine mode, physical memory, no PMP or cache, added memory latency 0 |
| Host limit | nice 15, at most two simulations, private `vex-fpu` and `sbt-fpu` locks |

| Native corpus | RV32IMAFC: C1 pass / strict Spike match | RV64IMAFDC: C1 pass / strict Spike match |
|---|---:|---:|
| riscv-tests | 12 / 12: uf 11, uc 1 | 24 / 24: uf 11, ud 12, uc 1 |
| ACT4 | 110 / 110: F 80, Zca 26, Zcf 4 | 236 / 236: F 84, D 116, Zca 32, Zcd 4 |
| Directed FP and basic FS context | 33 / 33 | 69 / 69 |
| Passing corpus total | 155 / 155 | 329 / 329 |
| Additional flags-only FS probe | 1 C1 fail; strict mstatus mismatch | 1 C1 fail; strict mstatus mismatch |

The passing corpus has 484 distinct test runs. The directed counts include
96 new self-checking FP programs and six older class/context programs.
Repeated legacy runs are counted once. Every passing run has a complete
C2/2 FP and CSR trace. Strict comparison checks integer and FP destination
bits, fflags, frm through fcsr, and the full mstatus snapshot at retirement.
No synchronization or mask is used. The extra failing probe is outside those
484 passes. It changes fflags with FEQ.S while FS remains Clean. See
[VEXII-FP-FS-001](../../FINDINGS.md#vexii-fp-fs-001).

| Flow | Result | Open |
|---|---|---|
| C1 / C2 | FP writes, actual FCSR/FS effects and retirement order captured; unexplained state changes fail capture | Overlapping or unretired effects are rejected; no transferred qualification to other pipelines |
| Coverage | All 1,425 RV32 S, 1,405 RV64 S and 1,525 RV64 D projected instruction/RM/source-class bins hit | 43,021 / 42,355 / 46,120 full flag crosses remain; operand-tuple closure is not claimed |
| Real lane simulation | 148,720 SoftFloat vector matches plus 1,820 Spike-derived vector matches | Seeded finite vectors, not a proof |
| Real lane formal | 36 obligations close, including 20 unrestricted signed W conversion proofs across all five RMs | 42 obligations time out at 60 seconds; unsigned/L and S/D conversion proofs not run |
| Basic lazy context | FS Off traps; Initial/Clean and FP-destination Dirty transitions pass on both widths | Flags-only Dirty defect; OS save/restore and S/U context switching not run |

See [coverage and generation](COVERAGE.md), [real-unit bindings and limits](datapath/README.md)
and the [ACT4 profiles](act4-64/README.md). The separate raw sqrt simulation
has another 100,000 normal-input vector matches. Its ten normal-case proof
attempts time out. These results do not establish whole-core qualification.

## Regenerate the corpus

Run from the workstation checkout. Put all output outside it. Set `VEXIIRISCV`
to the private pinned core. Set `RISCV_TESTS_SOURCE` to a riscv-tests checkout.
Set `ACT4_CHECKOUT` to the private pinned ACT4 checkout. Source the installed
JDK 21 and oss-cad-suite environment. Put RISC-V GCC on PATH.

```sh
export RVW_HOME="$PWD"
export RVW_FPU_RUN_ROOT="$VEXIIRISCV/fpu-runs-new"
export RISCVSIM_WORK="$VEXIIRISCV/rvw-fpu-build"
export RVW_VEX_LOCK=vex-fpu RVW_SBT_LOCK=sbt-fpu RVW_NICE=15
export RISCVSIM_MAKE_JOBS=2
mkdir -p "$RVW_FPU_RUN_ROOT"
nice -n 15 bash Cosim/build.sh "$RVW_FPU_RUN_ROOT/librvw_spike.so"
export RVW_SPIKE_SHIM="$RVW_FPU_RUN_ROOT/librvw_spike.so"
examples/vexiiriscv/rvw/fpu/build-tests.sh 32
examples/vexiiriscv/rvw/fpu/build-tests.sh 64
```

Build ACT4 with the profile below. Repeat with 64 in place of 32. On macOS,
use a private `XDG_CACHE_HOME` and the Z3 setup in [docs/ACT4.md](../../../../docs/ACT4.md).

```sh
nice -n 15 rvw regress act4-build \
  --profile examples/vexiiriscv/rvw/fpu/act4-32/profile.json \
  --checkout "$ACT4_CHECKOUT" --out "$RVW_FPU_RUN_ROOT/act432"
```

Generate the directed programs with [COVERAGE.md](COVERAGE.md). Add the
basic FS program from the privilege family. Keep the flags-only case in a
separate diagnostic run so its failure stays visible.

```sh
rvw privilege build examples/vexiiriscv/rvw/fpu/fs32.json --out "$RVW_FPU_RUN_ROOT/fs32"
cp "$RVW_FPU_RUN_ROOT/fs32/fp-context-fs.elf" "$RVW_FPU_RUN_ROOT/directed32/"
nice -n 15 rvw --project examples/vexiiriscv/rvw32fp.toml regress run \
  --suite fp-isa --source "$VEXIIRISCV" --jobs 2 --rvfi-trace --no-index \
  --out "$RVW_FPU_RUN_ROOT/isa32-run"
nice -n 15 rvw regress cosim "$RVW_FPU_RUN_ROOT/isa32-run" \
  --platform examples/vexiiriscv/rvw/platform32fp.json --json
```

Repeat for `fp-act4` into `act432-run` and `fp-directed` into `directed32-run`.
Repeat with the 64-bit project and platform. Reuse each cached configuration
build. Do not run the two profile campaigns with more than two total workers.
Regenerate and compile the older class and basic lazy-state programs as follows.
Use width 64, `rv64imafdc_zicsr_zifencei`, `lp64d` and the 64-bit linker
for the other profile.

```sh
rvw/.venv/bin/python examples/vexiiriscv/rvw/fpu/programs.py \
  --width 32 --seed 1 --random-cases 16 --out "$RVW_FPU_RUN_ROOT/directed32"
for name in classes lazy-fs; do
  nice -n 15 riscv64-unknown-elf-gcc -march=rv32imafc_zicsr_zifencei \
    -mabi=ilp32f -nostdlib -nostartfiles \
    -T examples/vexiiriscv/rvw/fpu/act4-32/link.ld \
    "$RVW_FPU_RUN_ROOT/directed32/$name.S" \
    -o "$RVW_FPU_RUN_ROOT/directed32/$name.elf"
done
```

Run `rvw privilege check` with the generated family and C1 test directory to
report each context bin. A failed case gets no coverage credit.

The adapter tests use Scala `FpCommitStateSpec` and `C2BackendSpec`.
The Python fast set has two unrelated launcher-niceness failures on this
nice-15 task: `test_launcher_reaches_nice_ten_once[1-3]` and `[2-0]` expect 10.
The task keeps nice 15. No physical hardware, full BOOM suite or OS context
campaign was run.
