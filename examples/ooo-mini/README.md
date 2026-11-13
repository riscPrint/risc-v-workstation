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

## Current M/U PMP measurements

These are finite simulation results on the default core. They are not full
privileged-ISA qualification, whole-core proof or C4 acceptance.

| Area | Measured result | Remaining work |
|---|---|---|
| Precise interrupts | MSIP, MTIP and MEIP pass self-checking programs and strict Spike trap comparisons. One qualified software interrupt enters with eight ROB entries occupied. | CLINT WFI passes 4/4 with declared synchronization. Directed PLIC passes strict offline and socket lockstep comparison with checked device evidence. Dynamic PLIC stimulus and other full-ROB IRQ sources remain open. |
| U-mode and four-entry PMP | 242 generated cases and one speculative-fault program pass with 243 strict matches. Matcher has 26 native cases. | S-mode, translation, ePMP and full privilege-family qualification are absent. |
| Isolation | One complete M-to-U PMP pair reports no_leak_observed. Both public windows are 21 cycles and have no denied load on the bus. | Other secrets, channels, policies and positive leakage controls. |
| Coverage snapshot | One 306-program batch reaches 80.40% line and 85.63% branch coverage. All pass. No exclusion is used. | ACT4, 405 unhit line points, 585 unhit branch points and incomplete logical-region attribution. This snapshot predates the final probe additions. |
| Formal snapshot | Seven depth-8 BMC goals time out. Two declared-trigger covers reach. ADD, LUI and retirement cover time out at depth 40. | No new property or ISA instruction proof closed. Long retries were not run. |
| Monitors and probes | Device-enabled cohort: 307/307 base cases and five device cases pass, 25 monitors with zero firings. Base has 304 strict matches and three explicit IRQ-synchronized matches. PLIC also passes strict socket lockstep. Three directed probe plans qualify. | Complete branch/age/byte/privilege coverage and consecutive-cycle recovery remain open. |

Detailed commands and limits: [interrupts](rvw/interrupts.md),
[devices and live comparison](rvw/devices.md), [protection](rvw/protection.md), [coverage](rvw/coverage.md),
[formal](rvw/formal.md), and [probes](rvw/probes.md).
The coverage snapshot is recorded in [PR #1296](https://github.com/riscPrint/risc-v-workstation/pull/1296).
The final probe cohort is recorded in [PR #1326](https://github.com/riscPrint/risc-v-workstation/pull/1326).
Their generated RTL identities differ. Do not merge their code-point universes.

## Initial M-mode measurements

Results apply to the recorded source hashes, configurations and programs.
They do not establish whole-core proof or release qualification.

| Tool | What the core gets | Measured result and limit |
|---|---|---|
| `rvw regress`, native C1 | ELF execution and repeatable results | All 50 RV32UI/M programs pass, including `ma_data`. Three directed programs also pass. |
| `rvw cosim check --strict`, commit-owned C2 | Architectural comparison with Spike | All 50 ISA traces match with zero synchronizations. Directed arithmetic, self-modifying code and trap/counter traces also strictly match. ISA has 18,154 retirements and 18,354 instruction records including trapping records. |
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
export RVW_SBT_LOCK=sbt-ooomini2
export RVW_OOO_LOCK=ooo-mini-ooomini2
"$RVW_HOME/scripts/with-lock.sh" "$RVW_SBT_LOCK" nice -n 10 sbt compile
rvw/build-programs.sh
rvw regress run --tier quick --rvfi-trace --out rvw/out/quick
rvw/build-isa.py /path/to/riscv-tests
rvw regress run --suite isa --rvfi-trace --out rvw/out/isa
rvw/compare-isa.py rvw/out/isa
```

The tested riscv-tests revision is `d7e86f701b929b5d801f8cda1a4871ab05f452bb`.
Third-party source stays outside this project. The C1 launcher builds the selected
source revision and honors RVW_SBT_LOCK and RVW_OOO_LOCK. Use private lock
names for your checkout. Keep RVW_OOO_LOCK different from the project lock.
The launcher lowers sbt and native Java priority. The adapter refuses unsupported observation modes.
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
synchronous trap. Reason 2 means a control redirect, including FENCE.I, MRET
and permission changes. Reason 3 means an interrupt.

Generate formal RTL and the design database before their tools:

```sh
"$RVW_HOME/scripts/with-lock.sh" "$RVW_SBT_LOCK" nice -n 10 sbt \
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
| [#1373](https://github.com/riscPrint/risc-v-workstation/pull/1373) | External PLIC evidence required dynamic mailboxes for a held source. Generic initial_levels supports this case. Unit tests retain pin, claim, completion and taken-event checks. |
| [#1310](https://github.com/riscPrint/risc-v-workstation/pull/1310) | C1 qualification compared retirement count with C2 records that include trapping instructions. The checker now reports a separate nontrapping count. Unit tests and the protection probe run verify the fix. |

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

## Bounded formal extension

The [M/U PMP formal run](rvw/formal.md) closes no property or ISA check.
Seven depth-8 property jobs time out. Two declared-trigger covers reach.
ADD, LUI and retirement cover time out at the measured-budget depth of 40.

## Qualified recovery observations

The [probe campaign](rvw/probes.md) passes 307 executions with 24 monitors
and zero firings. It qualifies a full-ROB interrupt, a discarded speculative
fault and forwarding before branch recovery. Consecutive-cycle recovery stays
unhit. These are finite observations, not whole-core proof.
## Dependency debug

The adapter accepts `--spinaltrace`. The generic simulator emits the PDG from
its instrumented report. The run loop records short wave windows and the
pre-edge C2 sample time in C1. Cycle zero is the first C2 sample.
Build the database with `runMain ooomini.BuildDb` in a private source copy.
Do not join a plain database and an instrumented wave without checking paths.

| Private extraction | Measured result |
|---|---|
| SpinalHDL 1.15.0, default core | 2 components; 2,175 signals; 3,703 assignments; 1,641 conditions; 9,422 edges |
| Elaboration / extraction | 12.6 s / 11.0 s |
| PDG / blocks / HGLDD export | 2.2 s / 1.4 s / 0.9 s |

These measurements establish extraction only. Dynamic attribution, typed wave
rendering and seeded bug hits need separate native wave checks.

## External debug

Standard external debug was not added in this campaign. The core lacks the
precise halt and abstract access path needed by a Debug Module. See the
[static integration decision](DEBUG.md). No native debug checks were run.

## Independent structure limits

The core has independent `issueEntries`, `loadEntries`, `storeEntries` and
`predictorEntries` parameters. The ROB stores the queue records. Capacity
controls allocation separately. Issue entries release at issue. Load and
store entries release at commit. Defaults are eight for each queue and 16
for prediction. `rob16` changes only ROB capacity. The earlier historical
ROB16 experiment also expanded implicit queues. It is not a one-structure
measurement of this implementation.

## Current structure matrix

All 45 RTL runs pass. All 45 complete traces match Spike. Decoded instruction
semantics match base on every variant. Seed is one. Added memory latency is
zero. The captures include the current M/U, PMP and interrupt core.

Six programs are shared with the NaxRiscv matrix. Three extra held-out
programs stress ROB, IQ and SQ capacity. All variants run the same nine ELFs.
The variants change only ROB 8 to 16, IQ 8 to 4, SQ 8 to 4, or the shared
predictor table 16 to 4. Load entries stay at eight. Physical registers stay
at 48. Counter reads synchronize six times per shared benchmark. The pressure
programs have no counter synchronization. No architectural differences are
masked.

### RTL IPC

| Program | Base | ROB16 | IQ4 | SQ4 | Predictor4 |
|---|---:|---:|---:|---:|---:|
| median | 0.825046 | 0.825046 | 0.825046 | 0.825046 | 0.749894 |
| qsort | 0.885618 | 0.885618 | 0.885618 | 0.885618 | 0.830667 |
| multiply | 0.980479 | 0.980479 | 0.980479 | 0.980479 | 0.970108 |
| towers | 0.941123 | 0.941123 | 0.941123 | 0.941123 | 0.919004 |
| vvadd | 0.988877 | 0.988877 | 0.988877 | 0.988877 | 0.988877 |
| memcpy | 0.997792 | 0.997792 | 0.997792 | 0.997792 | 0.997728 |
| rob-pressure | 0.327217 | 0.389800 | 0.327217 | 0.327217 | 0.327217 |
| iq-pressure | 0.279141 | 0.299835 | 0.261119 | 0.279141 | 0.279141 |
| sq-pressure | 0.254237 | 0.275229 | 0.254237 | 0.230769 | 0.254237 |

### Fixed base calibration

The model uses one shared non-pipelined multiply/divide port. These priors
come from `MulDiv.scala` and the core writeback register. Multiply uses four
issue-to-dependent cycles and a four-cycle issue interval. Divide uses 33
for both. This prevents false overlap of consecutive divide operations.
The priors apply to every variant. They are not fitted to a capacity result.

Branch penalty is the only fitted value. Base median, qsort and multiply
select one cycle from four candidates. No variant or held-out result enters
selection. Training MAE is 3.17%. Held-out MAE is 1.23% on the other six
base programs. Each prediction uses the frozen base C2 stream. RTL cycle
values do not enter prediction.

### IPC changes

A pair meets the criterion when its sign matches and error is at most half
of the measured change. A zero change requires a zero prediction. Values
are percent changes from base IPC.

| Variant | Program | RTL change (%) | Model change (%) | Criterion |
|---|---|---:|---:|---|
| rob16 | median | +0.0000 | +0.0000 | within |
| iq4 | median | +0.0000 | +0.0000 | within |
| sq4 | median | +0.0000 | +0.0000 | within |
| predictor4 | median | -9.1088 | -3.6687 | outside |
| rob16 | qsort | +0.0000 | +0.0000 | within |
| iq4 | qsort | +0.0000 | +0.0000 | within |
| sq4 | qsort | +0.0000 | +0.0000 | within |
| predictor4 | qsort | -6.2048 | -4.0524 | within |
| rob16 | multiply | +0.0000 | +0.0000 | within |
| iq4 | multiply | +0.0000 | +0.0000 | within |
| sq4 | multiply | +0.0000 | +0.0000 | within |
| predictor4 | multiply | -1.0577 | -1.3985 | within |
| rob16 | towers | +0.0000 | +0.0000 | within |
| iq4 | towers | +0.0000 | +0.0000 | within |
| sq4 | towers | +0.0000 | +0.0000 | within |
| predictor4 | towers | -2.3503 | -1.8186 | within |
| rob16 | vvadd | +0.0000 | +0.0000 | within |
| iq4 | vvadd | +0.0000 | +0.0000 | within |
| sq4 | vvadd | +0.0000 | +0.0000 | within |
| predictor4 | vvadd | +0.0000 | +0.0000 | within |
| rob16 | memcpy | +0.0000 | +0.0000 | within |
| iq4 | memcpy | +0.0000 | +0.0000 | within |
| sq4 | memcpy | +0.0000 | +0.0000 | within |
| predictor4 | memcpy | -0.0064 | -0.0064 | within |
| rob16 | rob-pressure | +19.1257 | +17.3592 | within |
| iq4 | rob-pressure | +0.0000 | +0.0000 | within |
| sq4 | rob-pressure | +0.0000 | +0.0000 | within |
| predictor4 | rob-pressure | +0.0000 | +0.0000 | within |
| rob16 | iq-pressure | +7.4135 | +7.8008 | within |
| iq4 | iq-pressure | -6.4562 | -6.7480 | within |
| sq4 | iq-pressure | +0.0000 | +0.0000 | within |
| predictor4 | iq-pressure | +0.0000 | +0.0000 | within |
| rob16 | sq-pressure | +8.2569 | +5.9314 | within |
| iq4 | sq-pressure | +0.0000 | +0.0000 | within |
| sq4 | sq-pressure | -9.2308 | -9.7869 | within |
| predictor4 | sq-pressure | +0.0000 | +0.0000 | within |

The model meets the criterion on 35/36 pairs and 9/10 nonzero changes.
All 36 directions match. Predictor4 median has the right direction but
underestimates the loss. The pressure programs supply nonzero capacity
changes. They prevent the 26 zero-change matches from dominating the claim.

| Structure | Direction / 9 | Direction and size / 9 | Observed coverage |
|---|---:|---:|---|
| ROB | 9 | 9 | 3 nonzero changes |
| IQ | 9 | 9 | 1 nonzero changes |
| SQ | 9 | 9 | 1 nonzero changes |
| Predictor | 9 | 8 | 5 nonzero changes |

All observed ROB, IQ and SQ pairs meet the criterion. Some predictor pairs
meet it. This is finite simulation evidence on a small cacheless scalar core.
The core trains prediction at commit. The component predictor trains at
issue. Cache, MMU, wider-core accuracy and an elaborated model snapshot
remain unchecked. Accuracy status stays inconclusive.

### Capture and replay limits

The matrix uses C1/C2 without per-cycle probes. The adapter avoids redundant
RAM settling waits when probes are off. It still settles an interrupt change
before it reads the selected load address. Probe rename fields also keep a
settling wait. The earlier [paired adapter control](adapter-control.json)
compares all C2 records and the end marker before and after the RAM change.
Both runs retire 10,653 instructions in 12,910 cycles on the pre-PMP core.
The refreshed core takes 12,912 cycles for that program. These are separate
source versions. All current matrix captures have complete Spike checks.

Incomplete ROB16 qsort attempts stay in [timeout receipts](matrix-interruptions.json).
They contribute no IPC. One 240-second retry was explicitly authorized. It
passed and matched all 226,061 instructions. All other limits stay at 120
seconds. The worker keeps inherited niceness instead of adding it repeatedly.

[RTL receipts](rvw/arch/matrix-results.json) retain source and capture hashes.
[Model receipts](rvw/arch/model-results.json) retain the fixed fit, every
change, per-program errors and engine identity. Raw captures and build output
stay outside Git. The full native ISA suite was not rerun for these variants.

Use `rvw/arch/build-pressure.sh SHARED_BENCH NEW_BENCH` to add the pressure
ELFs. Run `rvw/arch/matrix.py NEW_BENCH OUTPUT` with workstation Python and
private native and sbt lock names. Each batch uses one worker and preserves
the per-program wall limit. Run `rvw/arch/score-matrix.py OUTPUT NEW_MODEL`
to fit on the base training set and freeze predictions. Repeat scoring after
collection if it finishes early. `--allow-incomplete` writes an inconclusive
partial report. It never fills missing measurements with zero deltas.
