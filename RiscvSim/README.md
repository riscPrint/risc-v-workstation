# RiscvSim

Simulation runner for Spinal RISC-V cores, implementing the run contract (C1) and the RVFI trace
(C2) from [docs/PLATFORM_CONTRACTS.md](../docs/PLATFORM_CONTRACTS.md).

- `src/` is the generic library (package `riscvsim`), with no core-specific code: ELF loading,
  tohost decoding, the RVFI probe and trace writer, `result.json`, native-output capture for
  assertion messages, and the command-line driver (`build`, `run`, `run-many`, `info`) with
  a worker pool.
- `build.sbt` builds the generic library without a core checkout.
- `boom/` has a separate sbt build for BOOM's adapter (package `riscvsim.boom`). `boom/run.sh` is the command other tools call.

Status: `build`, `run`, `run-many` and `info` work on BOOM `small` (see "Verified"). The other
presets use the same code. Medium has a bounded throughput profile; large and
larger presets remain unqualified here.

The adapters require Verilator on `PATH`. Source the core environment script or
add the installed tools to `PATH` before use. `tests/programs/build.sh` uses
`riscv64-unknown-elf-gcc` on `PATH`; `RISCV_GCC` selects another executable.

The optional [medium thread profile](boom/benchmarks/README.md#opt-in-medium-launcher)
selects two runtime threads through the normal captured launcher. Use its
qualification limits before selecting it.

### Native checkpoint integration

`src/main/cpp/Checkpoint.h` saves a direct Verilator model and its context with
adapter-owned harness state. Build with `--savable`. Implement both `transfer`
overloads for all memory, devices, pending requests, RNG and monitor counters.
Call only after a settled edge. External host effects cause refusal. Validate
the Python native envelope before restore. Discard the model on restore errors.
This helper does not add save/restore to the Spinal JNI bridge or JVM scheduler.

`RvfiTraceWriter.checkpoint()` flushes and captures C2 prefix bytes, position,
digest, counters, order tracking and pending late-tval traps. Pass the decoded
JSON to the writer's `resume` argument in a fresh harness. The writer validates
header, position and digest before opening the destination. Resume into a new
run directory. The model and writer snapshots must come from the same stopped
boundary. The outer native envelope must bind the writer state to the model.

### Native device plugins

Projects can load native device models through `src/main/cpp/DevicePlugin.h`.
`DeviceDpi.cpp` supplies DPI-C bindings for open, close, MMIO and cycle/interrupt
updates. See [the device ABI](src/main/cpp/DEVICES.md) for configuration,
snapshot rules, error handling and the boundary of native qualification.

## Quick start

```sh
R=RiscvSim/boom/run.sh
scripts/with-lock.sh boom $R build --config small            # once per model; ~45 s cold
$R run --elf ../ref/riscv-tests/build/isa/rv64ui-p-add --out /tmp/add --seed 1
$R run --elf ELF --out DIR --json | jq .status               # stdout is only the result
```

Each launch holds the `boom` lock through sbt and the JVM. sbt runs offline and reuses
compiled Scala classes.
Each run elaborates BOOM. `run-many` elaborates once for each requested model.
Spinal reuses Verilator builds when the RTL and native inputs match.
Under regress, `RVW_CAPTURE_SOURCE_ENV` names the core checkout selector. Native identity
excludes that path because the generated RTL identifies the selected design. A core commit
alone does not change the native key. Other native inputs remain in the key.

## Command line (stable)

```
run.sh build    --config NAME[,NAME...] [--rvfi] [--wave] [--coverage] [--konata] [--json]
run.sh run      --elf PATH --out DIR [--config NAME] [--seed N] [--max-cycles N] [--mem-latency N]
                [--rvfi-trace] [--rvfi-check] [--wave [--wave-from CYCLE] [--wave-to CYCLE]]
                [--konata] [--coverage] [--wall-timeout S] [--json]
run.sh run-many --manifest jobs.jsonl [--jobs N] [--summary FILE] [--json] [defaults for every job]
run.sh identity [--config NAME] [--options JSON]
run.sh info     [--json]
```

- Configs: `small` (default), `medium`, `large`, `mega`, `giga`.
- `--seed` absent: a seed is picked and recorded. `--mem-latency` absent: randomized memory timing.
- `--max-cycles` default 200000. Cycles are counted from the first clock after reset.
- Integer limits are checked before model start. `--seed` accepts signed 32-bit integers.
  `--mem-latency` accepts 0..2147483647 cycles; 0 adds no delay. `--max-cycles` must be positive.
  Wave bounds are signed 64-bit integers: `--wave-from` must be non-negative and `--wave-to`
  must be positive and after `--wave-from`. `--jobs` accepts 1..2147483647.
- `--rvfi-trace` writes `rvfi.jsonl` (C2) and uses a model with RVFI and the riscv-formal monitor,
  so a monitor error ends the run as `rvfi_error`. `--rvfi-check` runs the monitor without a trace.
- Options are `--key value` or `--key=value`; dashes and underscores are the same.
- Relative paths are resolved against the caller's working directory (also in manifests).
- `--wall-timeout S` (manifest `wall_timeout`): wall-clock limit per run, counted from when its
  model is ready. The value must be finite and positive. `NaN`, infinities and numeric overflow
  are usage errors. A simulation still advancing ends at the limit; one that stops advancing is
  abandoned by a watchdog after the limit + max(2 s, 10%), and the batch goes on with a new worker
  (the stuck thread ends with the process). Both give `status: timeout` with
  `"wall_clock_timeout": true` (signature `timeout:wall-clock`), unlike a `--max-cycles` timeout.
- `identity` elaborates the requested models and emits their Verilog hashes with the native
  tool identity. It starts no simulation. Unknown native inputs refuse result reuse.
- Exit codes: `run` 0 pass, 1 fail/timeout/assert/rvfi_error, 2 harness error or bad usage.
  `run-many` 0 all pass, 1 some did not pass, 2 some harness error.
  Both commands use 3 for inconclusive evidence unless a harness error requires 2.
- stdout carries only the result: one summary line, or the JSON with `--json`. Progress goes to stderr.

`run` writes `DIR/result.json` (C1) and `DIR/run.log`, plus the requested artifacts. Extra keys
beyond C1: `details` (adapter facts: traps, tohost value, memory timing, model flags, RVFI record
counts, Konata desyncs) and `metrics` (`roi_cycles`, `roi_instret`, `roi_ipc` when the ELF has a
`bench_stats` symbol). `replay` writes to `DIR-replay` so it does not overwrite the original.
`result.json` is written to a temporary file and renamed, so a reader never sees half of it.

Adapters that call `RiscvSimConfig.elaborate` can pass `sourceRoots` as its
fourth argument. Use roots from the core project, not the launch directory.
The PDG extractor uses these roots to resolve Scala source files. The BOOM
adapter passes both source directories from `sourceDir`. Generated PDGs use
the existing absolute-path format. Portable fixtures must use project-relative
paths, and cross-checkout comparisons must remove only the checkout prefix.

## Benchmark ROI definition

The BOOM benchmark adapter reads two 64-bit words at `bench_stats`.
The benchmark runtime stores the `mcycle` and `minstret` deltas when `setStats(0)` follows
`setStats(1)`. These markers enclose the measured benchmark call. Input setup, optional
warmup calls, result checks and exit stay outside this interval. Counter reads and marker
call overhead remain part of this implementation's measurement. The ROI is not an exact
count of instructions in the benchmark function alone.

Use the same ELF hash, runtime, marker placement and adapter on both sides. Equal counter
names alone do not establish equal ROI boundaries. `metrics.roi_cycles` and
`metrics.roi_instret` identify these deltas. Whole-program `cycles` and `instret` identify
a different interval. Never combine the two origins in a performance comparison.
A failed run without both ROI words supplies no usable ROI sample.

Repeat a declared seed set with the same memory mode on both sides. Random-memory seeds
can change cycle counts even when ROI instruction counts stay equal. Fixed-latency seeds
need not sample that variation. C4 checks the largest paired relative loss. Means are
only descriptive. This rule estimates no population confidence. Keep failed seeds and
required workloads visible; they cannot be replaced by faster passing workloads.

## Artifacts

| File | When | What |
|---|---|---|
| `result.json` | always | C1 result |
| `run.log` | always | the run's harness lines, and native output (Verilator `$display`, simulator messages) printed while it was the only active run; output printed while other runs were active is left out (it is in the adapter's stderr), with one line saying so |
| `run.concurrent.log` | see below | the first attempt's log of a failure that was rerun alone |
| `rvfi.jsonl` | `--rvfi-trace` | C2 trace: header, one record per retirement in `order`, `trap` events, an `end` event |
| `wave.vcd` | `--wave` | VCD of the whole design. With `--wave-from/--wave-to`, dumping is switched on and off at those cycles inside the simulator (not cut afterwards). Time of cycle N = `details.wave_time_of_cycle_1 + (N - 1) * details.wave_time_per_cycle`. |
| `konata.log` | `--konata` | Konata pipeline log (spinal-boom's KonataTracer); `details.konata_desyncs` should be 0 |
| `coverage.dat` | `--coverage` | Verilator coverage of this run only. Source paths point at `details.rtl_dir`, a stable copy of the generated Verilog, so `verilator_coverage` can merge runs and annotate. |

`details` keys (generic): `concurrent` (other runs were active during this one), `serial_rerun`
(`first`: status and message of the concurrent attempt; `rerun_status`: the rerun's status, `not alone`,
`abandoned` or `no result`; `attributed`), `abandoned`.
Top-level `inconclusive` (C1): the reason a result is not evidence about the core. This includes
missing input capture and failures that cannot be attributed to one run (see "Failure messages
and concurrency" below).
`details` keys (BOOM): `traps`, `tohost`, `mem_timing`, `wave_time_per_cycle`, `wave_time_of_cycle_1`,
`model`, `model_compile_s`, `rtl_dir`, and when relevant `rvfi_records`, `rvfi_trap_records`,
`rvfi_order_gaps`, `rvfi_errcode`, `konata_desyncs`, `wave_window`, `bench_stats_partial`.

## Manifests (`run-many`)

One JSON object per line with `run`'s option names (`elf`, `out`, `config`, `seed`, `max_cycles`,
`mem_latency`, `rvfi_trace`, `wave`, `wave_from`, `wave_to`, `konata`, `coverage`, ...), dashes or
underscores. Options given on the `run-many` command line are defaults for every line. Blank lines
and lines starting with `#` are skipped. Before any job runs, every `out` must be (or become) a
writable directory, and no two jobs may name the same directory, compared by canonical path (a
symbolic link and its target, or `a/../b` and `b`, are one directory); otherwise it is a usage
error (exit 2) and nothing runs. `run` checks its `--out` the same way. One JVM elaborates each needed model once and runs the jobs
on `--jobs` threads. `--summary FILE` (and `--json` on stdout) writes `rvw.run-many/1`:
`{schema, core, manifest, jobs, workers, wall_s, counts: {pass: n, ...}, runs: [{elf, out, result,
status, seed, cycles, instret, wall_s, message}]}`.

Manifest integer numbers must be whole and within -9007199254740991..9007199254740991 because
the JSON library stores numbers as `Double`. For larger supported cycle bounds, use a quoted
base-10 integer, for example `"max_cycles": "9223372036854775807"`. The option's own range still
applies. Invalid job values and worker counts are usage errors before output setup or model start.

```sh
cat > jobs.jsonl <<'J'
{"elf": "../ref/riscv-tests/build/isa/rv64ui-p-add", "out": "out/add", "seed": 1}
{"elf": "../ref/riscv-tests/build/isa/rv64ui-p-sub", "out": "out/sub", "seed": 1, "rvfi_trace": true}
J
RiscvSim/boom/run.sh run-many --manifest jobs.jsonl --jobs 4 --summary out/summary.json
```

## Environment

| Variable | Default | Meaning |
|---|---|---|
| `SPINAL_BOOM` | `../../spinal-boom-eda` from `RiscvSim/` | BOOM checkout |
| `RISCVSIM_WORK` | `~/.cache/rvw/riscvsim/boom` | `cache/` shared Verilator builds, `ws/<pid>/` per-process workspace |
| `RISCVSIM_XMX` | `8g` | JVM heap |
| `RISCVSIM_MAKE_JOBS` | `4` | `make -j` for Verilator C++ builds |
| `RISCVSIM_KEEP_WS` | unset | keep the per-process workspace |
| `RISCVSIM_COVERAGE` | `line,user` | Verilator coverage kinds for `--coverage` models (`toggle`, `expr` also work; toggle makes `coverage.dat` about 230 MB per BOOM small run) |
| `RISCVSIM_EXTRA_INPUTS` | unset | nonempty declares an unsupported custom layout and refuses capture |
| `RVW_NO_LOCK` | unset | let run.sh run sbt without taking the `boom` lock |

## Decisions

- Each launch holds the `boom` lock through the JVM exit. This protects shared compiled
  classes from concurrent sbt writes. sbt runs offline and compiles incrementally. RiscvSim has no
  classpath snapshot cache. Each JVM elaborates each requested model once.
- `rtl_sha256` identifies the exact Verilog bytes used for a model. BOOM folds its optional
  RVFI monitor into this file. External Verilog includes and memory data files refuse identity.
- Run identity also includes the harness commit and dirty flag, captured ELF bytes, native
  tools, run options and native environment. Dirty harness inputs disable passing-result reuse.
- The native collector identifies tools once at start. Publication checks their file metadata.
  Compiler links preserve names such as `clang++`. Unknown native file or wrapper inputs
  disable reuse. Direct JVM launches remain inconclusive.
- Native cache entries need a verification receipt. Interrupted builds cannot leave reusable
  entries. Spinal keys native builds on the generated RTL within the native-tool namespace.
- The driver captures each ELF before model compilation. Loading, symbols and disassembly use
  the same bytes. `result.json` is replaced atomically.
- Concurrent native output has no job identity. Affected failures remain inconclusive until a
  serial rerun attributes them. The watchdog cannot replace an observed failure with a pass.
- Empty model or job lists, duplicate output directories and invalid options are usage errors.
- Gate accept requires committed revisions. See C1 and C8 for the shared evidence rules.

## Verification

The Scala suite checks the driver, ELF handling, RVFI records and simulation controls with a
small test design. Python tests check launcher cancellation and native identity. BOOM gate
checks cover only the selected tests and configuration. They do not prove the complete core.

## Limitations

- Each JVM elaborates every requested model, including on a Verilator cache hit. Use `run-many` for batches.
- A concurrent failure can require a serial rerun. A failure that cannot be attributed stays inconclusive.
- An abandoned simulation thread uses resources until the JVM exits.
- The current BOOM checks cover `small`. They do not cover `medium`, `large`, `mega` or `giga`.
- Software device stimulus and an inline cycle schedule are supported. See below.

## Tests

```sh
scripts/with-lock.sh sbt bash -c 'cd RiscvSim && sbt -J-Xmx4g -batch -Dsbt.offline=true "riscvsim/test"'
```

The driver rejects an ELF whose XLEN differs from `CoreAdapter.xlen` before model compilation.
It writes C1 `status: error` with both XLEN values.
`CoreAdapter.busBytes` defaults to `xlen / 8`. Pass it to `ToHost` and `MemWords`.
These helpers track 64-bit words and select data lanes from the store address and bus width.

The tests need a RISC-V GCC compiler. They build the small test ELFs on first use.
`RISCV_GCC` can select the compiler. Missing tools cause a test failure with a reason.
The suite covers the CLI, ELF handling, RVFI records, assertions, replay, output ownership,
watchdogs and concurrent failure attribution. RTL identity tests cover monitor bytes and
unsupported external data dependencies. Python launcher tests cover native identity,
compiler invocation names, cache reuse, changed flags and cancellation.

## Dependency trace model

`--spinaltrace` selects a separate model for `build`, `run`, `run-many` and
`identity`. It keeps trace probes and writes a dependency graph from the same
elaboration as the RTL. `details.model.spinaltrace` records the flag. Replay keeps
it. Each completed run copies the graph to the `pdg` artifact (`pdg.json`).
Use `--wave` to record the instrumented wave. Wave windows work as before.
An adapter must use `RiscvSimConfig.elaborate` to support this flag. A requested
model without its graph fails with an error. It cannot supply cause evidence.

The legacy `boom-spinaltrace` prototype is removed. Use the BOOM adapter with
`--spinaltrace`. BOOM small and VexRiscv have old/new caller-equivalence checks.
The checks retain design source locations, graph fields and accuracy metadata.
Equivalence of caller locations does not establish graph completeness.

Some generated statements have no retained core frame. The location filter
skips library frames and uses the elaboration caller. The prototype and the
normal helper then give different source files and lines. Statement names can
contain that file and line too. `CallerLocationSpec` tests this rule. Keep these
locations and names in the comparison. Keep the prototype while they differ;
do not map one helper to the other to claim exact parity.

## Interrupt schedules

BOOM and the VexRiscv example accept `--irq-schedule`:

```sh
RiscvSim/boom/run.sh run --elf RiscvSim/tests/programs/build/interrupt-timer \
  --out /tmp/irq-timer --seed 1 --mem-latency 0 --rvfi-trace \
  --irq-schedule '1:0x0,100:0x80,200:0x0,1000:0x80' --max-cycles 20000
```

Each pair gives a sampled cycle and the full input levels. Bits 3, 7, 9 and 11
select software, timer, supervisor external and machine external inputs.
A selected schedule replaces device-generated levels. C1 and replay keep the
schedule. C2 records each driven change. New levels affect the next clock edge.
The schedule does not change the RTL or the model cache key.

`tests/programs/interrupt-*.S` keep interrupts masked during a fixed loop.
They initialize writable status and trap-value CSRs before the loop.
They then enable machine delivery, or enter S mode with SEIP delegated.
The handler checks cause, EPC region and the cleared global enable bit.
The regression also checks these values outside the program and compares the
whole trace with Spike. The masked pulse and the later pending level are fixed
before simulation. Trap timing does not select the expected window.

Run the native regression with the core environment and RISC-V GCC on PATH:

```sh
RVW_INTERRUPT_RUNTIME=1 nice -n 10 rvw/.venv/bin/python -m pytest \
  rvw/tests/interrupts/test_runtime.py -q --basetemp=/tmp/irq-regression
```

This runs eight BOOM jobs in one model. Set `RVW_HOME` to this checkout and
`VEXRISCV` to its core checkout to also run eight VexRiscv jobs. The VexRiscv
programs use RV32 instructions and omit PMP setup because that core has no PMP.
Four masked runs per core end at their cycle limit.
Their timeout is expected and is not a program pass. Logs, C1, C2 and comparison
JSON stay in the selected temporary directory. The Python checker reports
`consistent` only for its schedule and window checks. Spike supplies the separate
instruction comparison. Missing bounds or trap evidence stays inconclusive.
Sail cannot synchronize external inputs and refuses this comparison.
## Additional test sources

See [test sources](../docs/TEST_SOURCES.md) for project-owned ACT4 and VM
suites. These use the existing ELF run contract. ACT4 expected signatures
must come from Sail or the suite, never from a DUT run.

## Multi-hart trace extension

`MultiHartTrace(file, header, hartIds)` is an adapter API. It writes C2/2.
Call `reset`, `retire`, `memory` and `complete` from accepted simulation events.
Call `outcome` for C1 completion aggregation. Close the writer before publishing
results. Each hart has its own epoch and retirement order. Capture sequence is
not a global architectural order. See C1/C2 in PLATFORM_CONTRACTS.md.
The CLI and BOOM adapter remain single-hart. Multi-hart Spike/Sail comparison
and a native two-core adapter are not supplied by this API.

Run its tests with the `sbt` lock:
`sbt -batch 'testOnly riscvsim.MultiHartSpec'` from `RiscvSim/`.

`TwoHartNativeSpec` runs two small RV32I-subset RTL fixtures through Verilator.
They share two words with round-robin backpressure. The producer writes 37.
The consumer polls it and writes 38. Each hart emits its own retirement order.
The original test uses x0/x1 and ADDI/LW/SW/BEQ encodings.
The shared fixture now also supports programmable word-atomic tests.
See [the ordering suite](tests/ordering/README.md#bounded-two-hart-rtl-fixture)
for concurrent observers, pinned herd comparison and injected faults.
They have no caches and are not full RISC-V cores. The test checks a known shared
memory result; it does not claim a Spike/Sail match or coherence RTL coverage.
Run it with `sbt -batch 'testOnly riscvsim.TwoHartNativeSpec'` under the `sbt` lock.

## Cache content scoreboard

`MemoryImage` holds independent expected bytes from test stimulus.
`CacheScoreboard` checks accepted fills, hits, stores and writebacks against it.
Give it line size, set count and associativity from project data.
Call `MemoryImage.write` with expected program writes before checking observed
cache stores. Never copy DUT read values into the oracle. Split cross-line
transactions in the adapter. Replacement requires explicit eviction; the generic
checker does not assume LRU. A denied fill cannot install a resident line.
Instruction invalidation is explicit. `CacheScoreboardSpec` tests self-modifying
code at the model level, separately from coherence.

Run: `sbt -batch 'testOnly riscvsim.CacheScoreboardSpec'` with the `sbt` lock.
These tests check the scoreboard. They do not establish RTL cache coverage.

## Coherence permissions

`CoherenceMonitor(lineBytes, clients)` checks normalized TileLink-C permissions:
N (None), B (Branch) and T (Trunk). Project adapters call `grant` only when a
Grant is accepted and `shrink` when a ProbeAck or Release completes.
Stalled requests must not change state. A branch grant requires intervention
of another trunk. A trunk grant requires all other copies to be invalidated.
Dirty shrink requires data. Use the cache scoreboard to check those bytes.
The monitor does not parse TileLink beats, track sinks or check GrantAck timing.
These require project channel adapters. It checks modeled permissions, not a
full implementation of TileLink-C.

Run: `sbt -batch 'testOnly riscvsim.CoherenceMonitorSpec'` with the `sbt` lock.

## Bounded forward progress

`ProgressMonitor(boundCycles, capacity, fairness)` tracks logical requests from
presentation through completion. Supply the project's arbitration and response
fairness assumptions as a nonempty string. Call `check` every sampled cycle.
Keep the same request ID on retry. Retry and unrelated completions cannot renew
its deadline. Check `finish` at campaign end; pending requests are not success.
The bound includes backpressure. A fairness violation can trigger the watchdog;
the monitor cannot distinguish that from a DUT progress failure without channel
evidence. Capacity is the declared outstanding resource limit.
This is a bounded test, not an unbounded liveness proof.

Run: `sbt -batch 'testOnly riscvsim.ProgressMonitorSpec'` with the `sbt` lock.

## DMA memory agent

`DmaAgent(backing, expected, snoop, capture)` operates on separate memory images.
The backing image is device-visible storage. Expected bytes come from test
stimulus. CPU writeback updates backing only after an accepted memory transfer.
`read` compares backing bytes with expected bytes. `write` applies the device
stimulus and byte mask to both images. The capture callback receives each accepted
transaction. Add its sampled cycle with `MultiHartTrace.memory` in the adapter.
Coherent requests require `DmaSnoop`. Its hooks must complete writeback before
read and invalidation before write. The agent does not invent those responses.
For noncoherent requests, the test must clean before device read and invalidate
a CPU copy after device write. A stale CPU observation fails the cache checker.
Concurrent CPU atomics need a project arbiter and captured serialization point;
the agent has no implicit thread synchronization or atomic reference backend.

Run: `sbt -batch 'testOnly riscvsim.DmaAgentSpec'` with the `sbt` lock.

## Limit ownership

Persistent simulation: [#14](https://github.com/riscPrint/risc-v-workstation/issues/14). Build/run performance: [#74](https://github.com/riscPrint/risc-v-workstation/issues/74). Dependency-model parity: [#68](https://github.com/riscPrint/risc-v-workstation/issues/68). Backend capabilities: [#116](https://github.com/riscPrint/risc-v-workstation/issues/116). Interrupt regression: [#47](https://github.com/riscPrint/risc-v-workstation/issues/47).

Retained limit: Unattributed concurrent failures and direct JVM identity remain inconclusive. Small-only BOOM qualification does not qualify other presets. Abandoned threads live until JVM exit. Unsupported external dependencies still refuse identity.

## FSM coverage version gate

Coverage models select explicit Verilator coverage kinds. The default is
`line,user,fsm` when the native `verilator -V` reports version 5.052 or later.
Older or unknown versions default to `line,user`. An explicit `fsm` request
on those versions fails before native compilation. Set `RISCVSIM_COVERAGE`
to select kinds from `line,user,toggle,expr,fsm`. The C1 model and replay record
the resolved list. Runs with different lists have different point universes.
Use the native `-V` version: an installed Perl launcher can report a stale
version with `--version`.

### WFI wake test

`tests/programs/wfi-timer.S` enables MTIP and executes WFI in a loop.
It accepts early WFI return. It requires no minimum sleep time.
The test drives MTIP after cycle 1000 with the schedule from #47.
It checks the independent trap window, entry CSR state and program completion.
It also compares the instruction trace with Spike.

```sh
RVW_WFI_RUNTIME=1 RVW_HOME="$PWD" VEXRISCV=/path/to/VexRiscv \
  nice -n 10 rvw/.venv/bin/python -m pytest \
  rvw/tests/devices/test_wfi_runtime.py -q
```

Each core runs at most 20000 cycles. The wall limit is 120 seconds after
simulation starts. The outer process limit includes lock wait and compilation.
The adapters hold their normal core and sbt locks.
This test does not check physical clock stop, privilege traps, debug wake,
or local reset. Those need adapter observations and project contracts.

## Atomic and ordering programs

See [the reusable ordering suites](tests/ordering/README.md). They build RV32/RV64
ELFs, validate assertions on Spike, and produce C1 random-timing manifests.
Reference and DUT results remain separate from ordering evidence.

## Persistent request server

`run.sh serve` reads one run-options JSON object per line from stdin. It writes
one compact `rvw.sim-server/1` response per line to stdout. The response has
`result` (a C1 result) or `error` (invalid request). CLI run options are defaults.
Send `{"op":"shutdown"}` or close stdin to stop. Send SIGTERM or SIGINT to the
launcher to cancel the current run and stop the whole process group.

Adapters must opt in with `CoreAdapter.freshInstancePerRun = true`. They must
construct a fresh native instance and fresh harness state for every run. The
server refuses adapters without this declaration. BOOM and VexRiscv opt in.
Other adapters report `reset: "adapter-defined"` in ordinary run metadata.

The server handles requests in order. It retains compiled models. Each request
uses a new native DUT instance and new adapter memory, random generator, device
state and trace writer. The seed is a run input. C1 `details.simulation_session`
records the process UUID, model run number, `reset: "new-native-instance"` and
native cache-hit flag. Existing RTL and native hashes bind model identity.
`details.execution_s` excludes model compilation. Source capture occurs at
server start. Restart after source edits.
C1 `execution_mode` is `server` for each server request and `process` for
ordinary runs. Error and abandoned results also record this field.

A failed run can be followed by another request. A watchdog-abandoned worker
poisons the server: it sends the timeout result and exits 2. It does not accept
another request. JVM exit stops abandoned simulation threads. The launcher owns
process-group teardown. There is no per-request cancellation that keeps the
server alive. The server holds the adapter's core lock for its full life.

For a manifest, use `run.sh run-many --persistent --jobs 1 --manifest jobs.jsonl`.
This calls the same serial server path. It records `execution_mode: "server"`.
It validates all output paths before starting. An abandoned worker stops the
batch. Later jobs have no result and the command exits 2.

In regression TOML, `backend = "riscvsim-verilator"` selects this path by default.
Set `[core] persistent = true` to select it for other compatible adapters.
Regression `--jobs N` uses separate server processes, each with a serial batch.
Each worker receives a serial batch. The runner skips the separate `build`
process. The server compiles each model once in the batch.
This avoids the extra elaboration in `build` followed by `run-many`.
The runner adds the skipped pre-build budget to the first-result startup budget.
Set `persistent = false` to disable this mode. It requires an adapter with `--persistent`
support and a fresh-instance declaration. It does not retain a JVM across
separate regression commands or suites.

## Timing measurements

`details.model_compile_s` measures the first model build in this JVM, including
elaboration and native setup. `details.model_timing.elaboration_s` measures
`RiscvSimConfig.elaborate`. `native_and_setup_s` is the remaining build time.
It includes native compilation or cache lookup, workspace setup and loading.
It is not a pure C++ compiler measurement. `details.execution_s` measures elapsed time after model readiness through result
preparation. It includes the adapter call, native-output draining and artifact
handling. It is not isolated adapter execution time. The launcher's sbt Scala compilation occurs before the JVM and
must be timed separately. Lock waits are not compiler time.

Use `SPINAL_VERILATOR_FLAGS` to test Verilator options, for example
`--threads 2`, `-O3` or `--output-split 10000`. Existing native input capture
includes these flags. A flag change gives a separate native cache identity.
Keep the seed, ELF and memory latency fixed. Compare C2 bytes and terminal C1
fields with a baseline. A faster run alone does not establish correctness.
Compiler wrappers such as ccache can disable native capture. Check the result's
`inconclusive` field before using it as evidence. Defaults remain unchanged.

## From-reset replay checkpoints

The native DUT and Spinal simulation scheduler cannot yet save live state.
The first checkpoint increment is a portable replay descriptor:

```sh
python3 RiscvSim/scripts/replay-checkpoint.py save \
  --result /tmp/first/result.json --cycle 50 --out /tmp/checkpoint.json
# Run the same captured ELF from reset with the same options, then:
python3 RiscvSim/scripts/replay-checkpoint.py verify \
  --checkpoint /tmp/checkpoint.json --result /tmp/replay/result.json
```

The descriptor binds the original C1 and C2 bytes, model, native build, source,
seed, timing inputs, IRQ schedule, terminal counters and selected trace suffix.
Verification refuses changed original evidence, input identity changes and
suffix differences. It reports `equivalent` only for the recorded replay suffix.
It does not establish ISA correctness. Keep external effects disabled. This
format supports only state derived from the captured ELF and C1 run options.
It does not restore DUT, device, memory, scheduler or random-generator state.
A replay still starts from reset. Native mid-run save/restore remains open.

### Source roots and caller equivalence

Core adapters must pass the core's Scala source roots to
`RiscvSimConfig.elaborate`. The VexRiscv example supplies its selected core root.
Without this argument, source files outside the adapter tree can remain bare
names. A bare name can be ambiguous when two packages use the same file name.
Run the Vex source regression with JDK 21 and `VEXRISCV` set to its checkout:

```sh
cd examples/vexriscv/rvw
sbt 'Test/runMain rvwvex.SourceRootsCheck'
```

Hold the workstation's `vex` and `sbt` locks around that command.

`rvw.debug.parity.compare` compares saved diagrams or computed traces. Supply
`kind='blocks'` or `kind='trace'`. Supply checkout prefixes as `left_roots` and
`right_roots`. An optional `callers` list contains tuples of
`(old_file, old_line, new_file, new_line)`. Use a mapping only after checking that
both frames identify the same elaboration operation. The function retains every
other source field. It checks generated caller names and diagram references too.
Use `source_files=[(old_file, new_file)]` for an audited file identity, such as
an unresolved basename and its absolute path. This changes no line or column.
Check the source package and the statement before declaring that identity.
If two packages contain the same basename, do not select the first search result.
Use the retained stack frame or audit the caller's imports and called method.
For traces, it retains edge kinds, edge multiplicity and accuracy metadata.
Duplicate vertex labels require an explicit identity mapping and are refused.

Caller equivalence does not mean identical source navigation. Each artifact
keeps its actual caller location. The old and new callers must both be available
for the source-navigation check. Do not map design-source statements to make a
comparison pass. Empty traces cannot establish parity. The removal cases are BOOM small and
VexRiscv; other cores and configurations need their own comparisons.

### BOOM MMU observations

With `--rvfi-trace`, BOOM also records `mmu-observations.jsonl`, named by
`details.mmu_observations` in C1. It samples the optional public PTW/cache
request and response signals and accepted physical TileLink A handshakes.
It changes no core source. See the [MMU format](../rvw/src/rvw/regress/README.md#privilege-controls-and-observation-reports).
Capture presence and event counts are observations, not protocol or PMA verdicts.

MMU capture also records changes to MSIP backing state as `device_state`.
The event states whether an IRQ schedule overrides device-driven interrupts.
This samples the harness device model separately from C2 memory effects. It
makes no device implementation or interrupt delivery claim.

## Firmware and Linux payload loading

`--elf-load-bias BYTES` adds a nonnegative decimal byte offset to ET_DYN
load addresses, entry and defined symbols. The default is zero. Use this only
for firmware that relocates itself, such as OpenSBI. The loader does not apply
ELF relocations or run a dynamic linker. It rejects ET_REL, PT_INTERP and a
nonzero bias for ET_EXEC. An ET_DYN file is not proof that it can relocate itself.
The adapter still owns reset PC and register state. Loading does not set them.

BOOM accepts `--boot-payloads loads.json` to load raw kernel, DTB and initramfs
bytes beside the firmware ELF. Other adapters must declare
`supportsBootPayloads` and call `ctx.loadMemory` before they can accept this
option. Paths below are relative to the manifest. Addresses and sizes are
strings. Use decimal or `0x` notation.

```json
{
  "schema": "rvw.boot-payloads/1",
  "ram": [{"base": "0x80000000", "size": "0x08000000"}],
  "payloads": [
    {"file": "Image", "address": "0x80200000"},
    {"file": "platform.dtb", "address": "0x87e00000"},
    {"file": "rootfs.cpio.gz", "address": "0x86000000"}
  ]
}
```

The driver captures all bytes before model compilation. `BootImage` rejects
out-of-RAM loads, overflow and overlap, including ELF BSS. It zero-fills BSS.
C1 `details.boot_payloads` records each captured file hash.
`details.boot_loads` records the effective addresses and memory sizes.
The manifest's RAM declaration is a placement check. The adapter must expose
that RAM. It does not change the RTL memory map.

This is a memory loader. BOOM still requires a `tohost` symbol and its existing
reset state. It has no Linux UART/PLIC adapter. See the project-owned
[Linux adapter plan](../examples/qemu-linux/rtl-adapter-plan.json).
No RTL Linux boot support follows from successful payload loading.

## Generated SoC maps

`run` and `run-many` accept `--soc-map PATH` (`soc_map` in manifests).
See the [SoC guide](../rvw/src/rvw/soc/README.md#runtime-maps-and-live-capture)
for region checks, device placement, captured bus requests and limits.

### RTL coverage tags

`riscvsim.RtlCoverage.tag(signal, Bin(...))` attaches a native Spinal tag.
A bin declares its ID, kind, domain, values, Scala source, and type name.
Kinds are `event`, `occupancy`, `state`, `transition`, and `arbitration`.
Domains are `committed`, `speculative`, and `structural`. A transition also
declares its `from` values. Multiple tags can describe one signal.

After emission, call `RtlCoverage.plan(report, designIdentity, clock, reset)`.
Write it with `RtlCoverage.write(plan, file)`. The result is `rvw.rtl-plan/1`.
The exporter prefixes IDs with exact instance paths. The sampler binds them to
the complete plan hash. Use a stable design revision or RTL hash as the design
identity. Tagged values use exact JSON integers with at most 52 signal bits.
Duplicate IDs, conflicting metadata and pruned signals fail export.

The exporter records annotations. It does not collect simulator samples.
An adapter must sample every declared signal before each rising edge and write
`rvw.rtl-samples/1`. See the coverage README. Unobserved bins do not become
unreachable. Native code coverage builds use `--coverage-per-instance` with Verilator 5.052
or newer. Older or unknown tools keep collapsed coverage.

The make wrapper checks the generated compiler metadata before it enables the
per-instance writer. It leaves shared-counter models under the native collapse
rule. Forcing a writer cannot recover instance observations from shared counters.

### Independent bus capture

BOOM `--rvfi-trace` also writes `memory-bus.jsonl`. It samples accepted A and D
handshakes at the external TileLink port. Source IDs, data, masks, response errors
and cycles come from bus wires. They do not come from retirement records.
See the [bus format](../docs/contracts/formal.md#passive-bus-observations).
The port is outside the caches. A cache hit has no external request. A D response
is not a device-side completion promise. FENCE checks must declare that boundary
and match requests from an independent test plan. This capture alone is not a
FENCE verdict. Device campaigns and cache-internal observers remain required.

Run the bounded native MMIO FENCE campaign with the core environment and GCC:

```sh
nice -n 10 rvw/.venv/bin/python RiscvSim/boom/tests/fence-device.py --out /tmp/fence-device-1
```

It runs I/I, I/O, O/I and O/O pairs with unique addresses in BOOM's uncached
interrupt-generator window. The sparse memory agent serves these extra offsets.
The plan comes from stimulus and matches actual accepted A/D handshakes.
Random memory timing uses the selected seed. The boundary ends at D acceptance;
there is no separate device execution queue. The program's tohost pass only
establishes completion. The separate comparison checks the four order edges.
R/W classes, device-side execution and concurrent target campaigns remain open.

### Instruction visibility observations

BOOM's optional `mmu-observations.jsonl` also records `icache_response` with
physical address, raw fetch data and byte width. It records `icache_invalidate`
with `refill_pending`, and accepted `icache_refill_request` addresses.
These are cache-stage observations. A response can be speculative or discarded.
It does not prove that the fetch buffer consumed those bytes after a fence.

`InstructionVisibility` checks consumed bytes against independent stimulus.
Use a unique publication ID for each patch. The adapter must observe data
visibility and the reader's local FENCE.I before `synchronize`. A writer's fence
cannot synchronize another hart. The project owns the release/acquire or
platform publication protocol. The checker refuses missing required observations.
BOOM also captures `fetch_consumed` at each decode-slot handshake, with its PC
and original instruction bits from the fetch buffer. These can still be on a
wrong path. Publication epochs must exclude entries killed by the fence redirect.
The byte checker is not yet connected to that epoch mapping. Pending-request
campaigns and cross-hart RTL publication remain open under #103.

CacheScoreboard accepts `replacement = "lru"` or `"fifo"` for projects with that
policy. Call `evict(..., replacementEviction = true)` for demand replacement.
Maintenance eviction does not use the replacement rule. LRU updates on reads
and nonempty stores. FIFO updates only on fills. The default `any` keeps the
existing capacity-only rule. Do not select LRU for a random-policy DUT.
BOOM bus capture also records accepted B probes, C releases/probe replies and
E grant acknowledgments. These keep permission parameters and dirty data on the
wire. A and D rows keep permission parameters; D also keeps the sink ID.
This is raw capture. Mapping it to cache scoreboards, checking virtual aliases
and injecting cache errors remain open under #109.

`DmaAgent` accepts an optional `DmaTransport` for a project RTL bus driver.
The transport must call `accepted` exactly once at the captured serialization
point. Read expectations are sampled there. CPU atomics that win arbitration
before the DMA read can update the independent expected image first.
DMA writes update expected bytes at acceptance, not when the request is queued.
If no transport is set, the agent uses simulation memory. External snoop hooks
own clean/invalidate completion unless the transport performs coherence under
its own serialization lock. A transport must not call `accepted` from retirement.
The bounded BOOM campaign below checks the native connection. Other fabrics
need their own adapters and campaigns.

`TileLinkDmaTransport` connects the DMA agent to Spinal's simulation memory
manager. It holds the manager's line lock while it sends actual B probes and
waits for C replies. Coherent reads downgrade dirty CPU copies. Coherent writes
invalidate CPU copies before the masked memory update. A transport read samples
the independent expected image at that serialization point. Split cross-line
transactions before calling this transport. Noncoherent transactions skip
snoops; the project must clean and invalidate CPU caches as needed.

`boom/tests/dma.S` and `riscvsim.boom.DmaCampaign` provide a bounded native BOOM
campaign. It checks dirty CPU data, coherent DMA reads and masked writes, CPU
invalidation and a CPU AMOADD. It checks a stale noncoherent device read and a
stale CPU read after a noncoherent device write. It invalidates the CPU copy
before publishing new data. MMIO phase barriers make the schedule explicit.
It also releases CPU AMOADD and a coherent DMA write without a phase barrier. A subsequent coherent read and the CPU old value must form one
of the two serial outcomes computed from fixed operands. DMA acceptance occurs
under the manager line lock. The old value arrives through MMIO, independently
of retirement. Two bounded DMA delays must observe both serial outcomes.
A finite campaign does not prove the whole fabric. Direct
test-main runs do not earn C1 gate acceptance. Keep them separate from
conclusive C1 ELF results.

Run that direct DMA campaign with `RiscvSim/boom/tests/run-dma.sh /tmp/dma-1`
after setting JDK 21, Verilator, GCC and `SPINAL_BOOM`. Use a fresh output path.
The script holds `boom`, then `sbt`. The native test has a 20000-cycle limit.
Use an outer process-group timeout for lock wait and native compilation.

### Bounded fairness and resource waits

`FairnessMonitor` samples every cycle. It measures environment enable gaps
separately from arbiter grant opportunities. Missing samples and missing client
grants cannot establish fairness. `ResourceWaitMonitor` checks a sampled graph
of exclusive resource owners and blocked requests. It reports a cycle separately
from an outstanding-request timeout. Adapters must supply actual resource waits.
The two-hart atomic fixture now measures its enable and grant wires separately.
It still has no cyclic resource fabric. Coherent-fabric dependency campaigns and
unbounded liveness proofs remain open under #128. None of these bounded monitors
proves eventual progress.

Direct native launches can set `RISCVSIM_REQUIRES=two_state,clock`. The shared
profile checker rejects unsupported needs before locks and native tools start.
See `rvw/src/rvw/sim/README.md` for regression suite declarations and limits.
### Serialized multi-hart reference

`SerializedMemoryReference` checks accepted memory actions at a project-declared
serialized boundary. Initialize it from captured input bytes. Supply expected
write bytes from independent program or device state. Its read method checks
observed bytes and returns the last write ID for each byte. It rejects missing
serialization IDs, duplicate action IDs and wrong data. Failed checks do not
advance the reference.

`TwoHartNativeSpec` uses this reference with independent register state for its
producer/consumer programs. It records memory serialization and read-from IDs
beside C2 hart retirement order. This fixture check does not add a full ISA
reference or production multi-image adapter. Use herd or another memory-model
checker for weak-memory outcomes. Do not impose this serialized model on a
boundary that permits other legal interleavings.

### Native coherent cache checks

`CoherentCacheNativeSpec` runs SpinalHDL's `CacheFiber` writeback cache in native
Verilator. The cache has one way, 1024 bytes and 64-byte lines. Two simulated
TileLink coherent clients share its 64-bit port. The clients are test agents,
not CPU implementations.

Spinal's TileLink monitors aggregate accepted A/C/D beats. The test connects
completed permission changes to `CoherenceMonitor`. It compares response,
intervention and writeback bytes with a separate stimulus-owned `MemoryImage`.
It initializes both reference and backing RAM from the same input bytes.
Expected data never comes from DUT reads.

The directed test dirties a client line and requests shared ownership from the
other client. It releases both clients, then overlaps two exclusive requests.
It holds D acceptance for 80 cycles and requires both A requests to be accepted
before release. Random channel stalls add backpressure. A same-set alias must
evict dirty cache data that has not yet reached backing RAM. The test requires
an observed writeback and checks final backing bytes. Missing interventions,
releases, writebacks, stalls or request overlap fail the test.

A second run corrupts an untouched backing byte while retaining the correct
reference image. It must fail with `cache response byte mismatch`. The wrapper
checks `TilelinkTester.checkErrors()` because that helper records simulation
exceptions instead of immediately throwing them.

Run with the `sbt` lock:

```sh
(cd RiscvSim && ../scripts/with-lock.sh sbt nice -n 10 sbt -batch \
  -J-XX:ActiveProcessorCount=2 'testOnly riscvsim.CoherentCacheNativeSpec')
```

These are bounded cache-module checks for the declared configuration and seed.
They are not a proof of all interleavings or coherence in a CPU integration.


## Online co-simulation

`rvw cosim live` can launch a C1 adapter and check its C2 file during the run.
See [the cosim launch command](../Cosim/README.md#launch-a-simulator-with-online-checking).
The launcher sets `RVW_RVFI_FLUSH=1`. `RvfiTraceWriter` then flushes its header,
retirement records and events before returning. The default stays buffered.
This option changes output delivery. It does not add C2 v2 state observations.
The writer constructor also accepts `flushEachRecord` for adapter tests.

## Simulation speed metrics

C1 records `metrics.sim_khz` and `metrics.sim_instructions_per_s` from the
unrounded `details.execution_s`. Model setup is excluded. Adapter execution,
trace writes and artifact handling are included. The dashboard plots recorded
C3 rates per preset. These rates do not prove correctness. Use long workloads,
fixed seed and memory latency, and serial runs. Keep tracing options equal.
See `rvw regress speed-compare --help` for repeated, equivalence-gated comparisons.

The [Linux startup example](../examples/qemu-linux/README.md#bounded-linux-startup-payloads)
prepares reset firmware, kernel, initramfs and a final DTB for `--boot-payloads`.
A separate fixed-image QEMU check uses the same payload bytes. The project
software device composition does not connect the BOOM RTL bus. A startup
prefix comparison must not be reported as a Linux RTL boot.

`PersistentNativeSpec` tests a tiny accumulator with one reused compiled model.
It checks fresh DUT, PRNG, tohost device and progress-monitor state after three
injected simulation failures and across repeated successful requests. It is a
bounded native test. It does not qualify all core devices, native process
cancellation, coverage reset or long-lived resource use.

## Per-slot CSR observations

Pass `csrSlots: Seq[Map[Int, Data]]` to `RvfiProbe`. Each map selects independent
DUT signals for one RVFI channel. The key is the numeric CSR address. All slots
must have the same address set. Signals must hold the state after that slot,
including its synchronous trap entry. Do not connect a cycle-final CSR bank
to every slot. The probe samples each map with its channel before sorting by
retirement order.

Add `csr_snapshot` to the trace writer header with the same hex addresses.
The writer selects C2/2 and the `csr` capability. Each record must contain the
complete declared set. Missing or undeclared observations cause an error.
No CSR state is copied from the reference. Core adapters must expose the
per-slot signals. This API does not add those signals to a core. The existing
BOOM adapter does not yet select these observations. Sail full-state CSR
snapshots remain unavailable through its current public write log.

### Per-hart ELF inputs

An adapter can override `hartIds(config)` with its supported hart IDs. Pass
`--hart-images images.json` to `run` or in a run-many manifest. Generate that
file with `rvw memory images --hart-image 0=hart0.elf --hart-image 1=hart1.elf`.
The existing `--elf` selects the primary image for legacy C1 metadata. Each
hart starts at the entry of its captured ELF. The driver captures and checks
all image hashes before compilation. `ctx.loadMemory` loads all segments into
one shared memory. Identical shared segments load once. Conflicting segments,
including BSS, fail before memory writes. Boot payloads cannot be combined.

Use `ctx.hartImages` for per-hart entries. Construct `MultiHartSession` with
one `RvfiProbe` per hart. Call `reset` when each hart resets. Call `sample`
once per cycle, then `complete` for each hart result. Forward accepted memory
actions with `memory`. Return `outcome` when the run ends. Close the session
on all paths. Missing completion gives timeout. Different harts have separate
RVFI orders. Capture order is not memory order.

This is an opt-in generic adapter path. Existing single-hart adapters reject
these inputs. No production core integration or multi-hart ISA result is
claimed by the driver tests.

### Independent atomic observer

`AtomicMemoryObserver` checks a declared serialized memory boundary. Supply
initial bytes and each operand from independent stimulus or architectural
reference state. Call its methods for accepted actions, with consecutive
serialization IDs. It checks LR values, matching SC reservations, failed SC
byte retention, all nine word/doubleword AMOs and word/doubleword/quadword CAS.
Observed bytes never update the reference image. Stores invalidate overlapping
reservation sets of the declared power-of-two size. This is a project policy.

The SC failure limit applies only when the caller certifies a constrained loop
and the named service condition holds. It is a bounded project service check,
not an ISA limit on spurious failures. Use `ProgressMonitor` with a persistent
logical request ID to detect missing attempts or cycle-based livelock. No
unbounded eventuality or aq/rl ordering follows from these byte checks. Bind
accepted actions and independent operands in the project adapter before using
this observer for RTL. The unit tests supply model events only.

### Project cache observer events

`CacheEventObserver` maps project event names to cache and consumed-fetch
checks. Pass the event-name map at construction. Each event has `cycle`,
`hart` and a project `event` name. Addresses are nonnegative byte offsets in
the independent `MemoryImage`. Use `physical_address` for the offset and
optional `virtual_address` to record aliases. Byte strings use hex byte order.

Cache event kinds are fill, denied, read, store, evict and invalidate. Store
also needs a hex byte `mask`. Update the independent oracle from stimulus
before the accepted store. Evict can carry writeback bytes and a replacement
flag. Publish and sync use the existing instruction visibility checker. Sync
needs both `data_visible` and `fence_i_complete`. The project must observe its
publication protocol before it sets those fields.

Fetch request, reply, consume and discard events use a stable `id`. A request
also names its `publication`. Only consumed bytes count as instruction checks.
Finish requires explicit event coverage and no outstanding fetch requests.
Map accepted project events in the adapter. The tests cover event mapping,
physical aliases, pending cross-hart publication and injected stale bytes.
They do not establish RTL cache error injection or replacement coverage.

### Live state through the Spinal bridge

`BridgeState.instrument(config)` exposes synchronous registers and memories.
`capture()` reads their current values. `restore(state)` checks the complete
layout and widths before it writes any value. The adapter must stop with the
clock low and settled. It must also save RAM, input values, bus transactions,
C2 writer state and counters. It must restore these before the next edge.
Do not use this API for latches, blackboxes or asynchronous clocks.
The API does not save a Scala scheduler. See the VexRiscv checkpoint probe for
an explicit cycle loop that needs no saved threads.

### Hart lifecycle and shared interrupt resources

`HartLifecycleObserver` checks project-normalized HSM-style start, started,
stop and stopped events. A start declares the entry PC and opaque argument.
Both must match the observed start. Pending transitions retain a bounded
watchdog. Independent reset advances only that hart's epoch and invokes the
project callback for local observer reset. `startedAfterReset` states the
project reset policy. Shared IPI state remains pending across hart reset by
default. Set `resetClearsIpi` only when the platform declares that behavior.

IPI sends coalesce per target. Observe each hart's MSIP input separately.
Shared interrupt claims have one owner. Completion must come from that owner.
`requireClaimsDrained` is a project stop/reset policy, not an SBI architectural
requirement. Finish requires all expected hart states and no incomplete claims
or transitions. The tests drive observer events. SBI firmware, CLINT timer
comparators, PLIC arbitration RTL and real hotplug campaigns remain open.

## Probe events

`run --probes` builds a model with the core's `spinalprobes.Probe` calls enabled. The
adapter samples them with `ProbeCollector` in its cycle loop and writes
`probe-events.jsonl` (`rvw.probe-events/1`, C1 artifact `probe_events`). See
[SpinalProbes](../SpinalProbes/README.md) for the API and `rvw probes` for the converters.
An adapter declares `supportsProbes`; otherwise the flag is refused.

## SystemC and TLM memory target

`src/main/cpp/TlmMemory.h` provides a blocking TLM-2 memory target with byte
enables and range checks. The [native example](examples/systemc/README.md)
builds an RTL requester with Verilator `--sc` and connects it through a
SystemC initiator bridge. The target annotates delay. The caller consumes it.
The example uses one outstanding transaction and explicit clock-edge sampling.
Its native test passed with SystemC 3.0.2 and Verilator 5.049. This is a small
partition example. It provides no whole-core or timing qualification.

## Fault injection (`--fault`)

`run --fault FILE` applies C1 faults (`rvw.fault/1`, see `rvw/src/rvw/fault/README.md`)
in any adapter that runs through `SimSession`. The adapter needs no code for it.

- The job uses a separate `_fault` model. Elaboration tags every register
  `simPublic`, and Verilator builds with `--public-flat-rw`, so outside writes
  re-evaluate the logic that reads the register. Golden runs keep the normal model.
- `site` is the design database path: instance names below the toplevel, then the
  Verilog signal name (`rvw fault sites --db DB`).
- `stuck0`/`stuck1` set the bit after each clock edge from `cycle` for `duration`
  cycles, or to the end. `flip` inverts it once at `cycle`. Cycles are the driver's
  sampled-cycle count.
- The injector reads the register back one time unit after the first write.
  `details.fault` is `applied: true` only when the read-back shows the forced bit.
  It records `applied_cycle`, `before`, `after` and `writes`. A missing site, an
  enumeration register, a bit outside the register, a run that ends first or a
  failed read-back gives `applied: false` with a reason.

Faults on RVFI-only registers (for example VexRiscv `*FORMAL*` stage registers)
change only the trace. Exclude them with `rvw fault plan --exclude` for functional
estimates.

Measured on 2026-11-13 with the VexRiscv example (`rv32im`, smoke program, 91 cycles):
a 12-fault seeded plan over the design database (`--exclude '*FORMAL*'`, window 10:80,
seed 7) applied and confirmed 11 faults. Results: 2 detected (simulation asserts),
4 timeouts, 5 safe, 1 `not_injected` (`CsrPlugin_satp_PPN`, absent from the current
M-only model because the database came from an older configuration).
### Native co-simulation transport

An adapter can expose `LockstepDpi` and use its `observe` method as the
`RvfiTraceWriter` callback. Set `RVW_COSIM_DPI=1` when compiling and running
that adapter. The generic Verilator configuration links the native C2 client.
The callback must run in a simulation thread, outside a clock-edge callback.
The core clock must remain stopped until the callback returns. Send the end
record before the native simulation closes. `rvw cosim live --lockstep` owns
the reference connection. The default writer still uses the Scala transport.
