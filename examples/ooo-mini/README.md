# OoO Mini

OoO Mini is a cacheless RV32IM core on SpinalHDL 1.15.0 and Scala 2.13.14.
It fetches and renames one instruction per cycle. It issues ready instructions
out of order and commits one instruction per cycle in program order.
It executes real RISC-V ELFs. It does not instantiate the tiny OoO fixture.

The default core has eight ROB slots and 48 physical registers. `rob16` changes
the ROB to sixteen slots. The ROB slots also hold the issue and load/store queues.
A map table and free bitmap implement rename. Recovery restores the committed map
and releases younger physical destinations. Loads wait for older stores to resolve.
Byte forwarding selects the youngest older matching store. Stores reach RAM only
at commit. A 16-entry bimodal predictor and tagged BTB predict fetch addresses.
Multiply completes after three cycles. Restoring division computes one quotient
bit per cycle and completes after 32 cycles. Branches resolve at issue and recover
at commit. `FENCE.I` discards younger fetched instructions at commit.

The instruction port supplies one word at `fetch`. The data port supplies four
little-endian bytes starting at `loadAddress`, including unaligned addresses.
RAM must respond without a wait state. There are no caches, translation,
compressed instructions, atomics or floating-point instructions.
The M/U CSR bank and four PMP entries support the selected tests. Full privileged ISA compliance
has not been established. The fixture supplied the committed-map recovery pattern;
its two-register payload interface is not a component of this core.

## Measured results

Results apply to the recorded source hashes, configurations and programs.
They do not establish whole-core proof or release qualification.

| Tool | What the core gets | Measured result and limit |
|---|---|---|
| `rvw regress`, native C1 | ELF execution and repeatable results | All 50 RV32UI/M programs pass, including `ma_data`. Three directed programs also pass. |
| `rvw cosim --strict`, commit-owned C2 | Architectural comparison with Spike | All 50 ISA traces match with zero synchronizations. Directed arithmetic, self-modifying code and trap/counter traces also strictly match. ISA has 18,154 retirements and 18,354 instruction records including trapping records. |
| `SpinalProbes`, `rvw perf topdown` | Native branch, rename, occupancy, recovery and commit observations | Smoke has 54 commit slots: 17 retiring, 35 waiting at a nonempty ROB head and two empty-ROB slots. The partition agrees with C2. It is a project commit-slot partition, not hardware top-down signoff. |
| Kanata conversion | Allocation, issue, commit and squash view | The trap/counter sample has 49 retirements, 24 flushed instructions, two open instructions at termination and zero orphan events. A trapping head is flushed, not retired. |
| `rvw csim compare-rtl` | Predictor comparison with project parameters | Four smoke branches were compared. Conditional direction has zero disagreements. One jump has a target-status classification difference. The model remains approximate. |
| Scala property DSL, `rvw checks generate --all` | Properties beside RTL and project-bound microarchitecture checks | Fourteen properties feed 19 native monitors. Eight SV binds check bounds, free/live disjointness, age order, byte forwarding and recovery FIFO order. All 50 default ISA runs pass with these binds and Verilator assertions enabled. No check fires. ROB16 uses the Scala monitors only. |
| `rvw formal regress` | Small bounded checks from generated assertions | Five depth-8 bounded-pass observations have reached covers. Overall remains `unknown`: input closure and universal activation are not certified. Predicate covers do not prove every logical antecedent occurred. |
| `rvw formal isa` | Direct RTL RVFI instruction-check wrapper | ADD, LUI and retirement cover timed out after 15 seconds at depth 8. No ISA check closed. No unbounded proof was run. |
| `rvw ooo` | A trace-driven timing estimate and structural experiment | Three programs ran on both ROB sizes. The window test predicts a 1.774 IPC ratio and measures 1.206. The model overpredicts the benefit. No accuracy qualification is claimed. |
| `rvw fault` | Confirmed register injection and C2 classification | Four flips in rename/ROB registers: two detected, two safe, none unresolved. This is a four-sample exercise. |
| `rvw lint`, SpinalDB | Native lint, rule findings and clock/reset inventory | 100 active findings and 159 unresolved generated-temporary candidates remain. The database has 501 registers and one clock. No structural CDC/RDC crossings were found. This is not clean lint or CDC signoff. |
| `rvw cov` | Raw code points and functional observations | Smoke and trap programs hit 3,436 of 5,121 code points. Line coverage is 60.24%; branch coverage is 71.37%. Functional coverage records 52 mnemonic/mode bins on ISA traces. No complete mnemonic expectation plan is declared. |
| `rvw regress gate` | Committed negative and positive controls | The three-program gate with seed 17 rejects a planted multiplier bit error for one new failure and accepts the committed repair. No waiver or allow-missing flag is used. |

Detailed tables: [ISA](isa-results.json), [interfaces](interfaces-results.json),
[formal](formal-results.json), [timing](timing-results.json), and
[qualification](qualification-results.json).

The native issue-stage stream also demonstrates issue reordering. The dependent
benchmark records 200 issued IDs below an ID already issued. IDs follow allocation
order. This observation includes speculative instructions. It is separate from
architectural correctness, which the C2 comparison checks.

## Build and run

Set `RVW_HOME` to the installed workstation checkout. Use its native-tool setup.
Put RISC-V GCC and `rvw` on `PATH`. Run from this directory:

```sh
"$RVW_HOME/scripts/with-lock.sh" sbt-mem nice -n 10 sbt compile
rvw/build-programs.sh
rvw regress run --tier quick --rvfi-trace --out rvw/out/quick
rvw/build-isa.py /path/to/riscv-tests
rvw regress run --suite isa --rvfi-trace --out rvw/out/isa
rvw/compare-isa.py rvw/out/isa
```

The tested riscv-tests revision is `d7e86f701b929b5d801f8cda1a4871ab05f452bb`.
Third-party source stays outside this project. The C1 launcher builds the selected
source revision and uses `sbt-mem` and `ooo-mini-mem` private locks. It lowers sbt
and native Java priority. The adapter refuses unsupported observation modes.
Use probe conversion for Kanata. Native runtime RVFI checking and SpinalTrace
are not mapped. Complete RTL identity capture is not qualified.

```sh
rvw/run.sh run --elf rvw/out/programs/smoke --out rvw/out/probes \
  --rvfi-trace --probes --seed 17
rvw probes convert rvw/out/probes/probe-events.jsonl --to kanata \
  --out rvw/out/probes/konata.log
rvw perf topdown rvw/out/probes/probe-events.jsonl \
  --c2 rvw/out/probes/rvfi.jsonl --json
rvw probes convert rvw/out/probes/probe-events.jsonl --to bp-events \
  --c2 rvw/out/probes/rvfi.jsonl --out rvw/out/probes/bp.jsonl
rvw csim compare-rtl predictor-study.json --trace rvw/out/probes/rvfi.jsonl \
  --events rvw/out/probes/bp.jsonl --json
```

Open the converted log with a Kanata-compatible viewer. Probe reason 1 means a
trap. Reason 2 means another control redirect, including `FENCE.I`.

Generate formal RTL and the design database before their tools:

```sh
"$RVW_HOME/scripts/with-lock.sh" sbt-mem nice -n 10 sbt \
  'runMain ooomini.Generate' 'runMain ooomini.BuildDb'
rvw checks generate --all --out rvw/out/lint-bindings
rvw lint --settings lint.json --json
python3 rvw/prepare-formal.py
rvw formal regress rvw/out/formal-jobs/regress.toml \
  --out rvw/out/formal --jobs 2 --timeout 15
```

Set `RISCV_FORMAL` to a pinned riscv-formal checkout only for the ISA profile:

```sh
rvw formal isa --project formal.toml --out rvw/out/isa-formal --timeout 15
```

The wrapper leaves RAM data arbitrary. It does not prove the memory system.
Commands that create result directories require a fresh output name.

## Timing model

`rvw/timing.json` describes the eight-entry core. `rvw/timing-rob16.json` changes
capacity to sixteen. Parameters are project declarations, not an elaboration export.
The three programs are under `rvw/bench/`. All six native runs pass.

| Program | RTL cycles, 8 slots | RTL cycles, 16 slots | Model cycles, 8 slots | Model cycles, 16 slots |
|---|---:|---:|---:|---:|
| window | 4024 | 3338 | 4213 | 2375 |
| dependent | 618 | 618 | 909 | 909 |
| forward | 514 | 514 | 908 | 908 |

Both IPC ratios are 1.0 on the dependent and forwarding programs. The model lacks
wrong-path execution. Branch timing and shared multiply/divide occupancy differ
from RTL. The predictor study trains in retirement order; RTL predicts at fetch
and trains at commit. These differences remain explicit.

## Controls and fixes

`python3 rvw/gate-controls.py` creates committed good, planted-bug and repair
controls without changing the worktree or real index. It flips the multiplier's
low result bit in the bug commit. Compare GOOD with BUG, then GOOD with FIX using
`rvw regress gate --tier quick --base-rev GOOD --cand-rev CANDIDATE`.
The recorded control history is retained on
[`test/ooo-mini-gate-controls-20261113-mem`](https://github.com/riscPrint/risc-v-workstation/tree/test/ooo-mini-gate-controls-20261113-mem).

Directed tests also found core defects. Self-modifying code exposed stale ROB
instructions after `FENCE.I`. The trap test exposed `minstret` counting trapping
instructions. Both fail before their fixes and pass after them. Strict Spike
comparison confirms the corrected instruction and counter values. Reserved
encodings and trap entry/return execute in the directed tests. The C2 traces
do not carry a full CSR-state snapshot.

Each workstation problem found during this integration has its own generic fix:

| PR | Problem and validation |
|---|---|
| [#1192](https://github.com/riscPrint/risc-v-workstation/pull/1192) | Generated FIFO monitors lacked an idle/simultaneous-transfer case. Two native lint regressions fail before the fix and pass after it. |
| [#1196](https://github.com/riscPrint/risc-v-workstation/pull/1196) | Revision checkout tried to clone a core subdirectory as a Git repository. The regression checks historical bytes, sibling dependencies and preservation of the dirty input tree. |
| [#1200](https://github.com/riscPrint/risc-v-workstation/pull/1200) | Source-scope conditions were reported as established latches for generated temporaries. They remain unresolved and lint stays inconclusive. Named partial-assignment findings remain. |
| [#1220](https://github.com/riscPrint/risc-v-workstation/pull/1220) | Scalar memory preflight blocked illegal RV32 LD/SD encodings before Spike could trap. Ten native tests cover illegal encodings and retained split-access refusals. |

Implementation and evidence were merged in
[#1175](https://github.com/riscPrint/risc-v-workstation/pull/1175),
[#1184](https://github.com/riscPrint/risc-v-workstation/pull/1184),
[#1187](https://github.com/riscPrint/risc-v-workstation/pull/1187),
[#1203](https://github.com/riscPrint/risc-v-workstation/pull/1203), and
[#1245](https://github.com/riscPrint/risc-v-workstation/pull/1245).

## Typed LSU retry smoke

[The retry receipt](retry-results.json) retains capture hashes, live-ID checks,
retry-to-completion histograms and a complete Spike match. The retire probe
count equals C1 `instret`. Cache retry uses the explicit LSU response.
The mini core declares four zero-valid retry probes because it has no
rejected LSU attempts. Zero activation is not exercised retry behavior.
Only the NaxRiscv cache cause activates in these two short runs. Other
causes still need directed captures. Completion spans include queue and
service time. They are not isolated replay penalties.

## Machine interrupt extension

The core now has MSIP, MTIP and MEIP inputs with commit-boundary recovery.
See [interrupt checks](rvw/interrupts.md) for the commands and limits.
The measured tables above predate this extension. New runtime measurements
are separate from those historical results.

## U-mode and PMP extension

See [protection checks](rvw/protection.md) for 243 passing RTL cases with
243 strict Spike matches, the matcher tests and one bounded isolation pair.
These results are separate from the historical coverage and formal tables.

## Bounded coverage extension

The [306-program campaign](rvw/coverage.md) reaches 80.40% line and 85.63%
branch coverage on the M/U PMP core. All runs pass with zero monitor firings.
ACT4 and complete functional coverage of each logical OoO block remain open.
