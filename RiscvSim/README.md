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
presets build through the same code but were not run.

The adapters require Verilator on `PATH`. Source the core environment script or
add the installed tools to `PATH` before use. `tests/programs/build.sh` uses
`riscv64-unknown-elf-gcc` on `PATH`; `RISCV_GCC` selects another executable.

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

The `boom-spinaltrace` prototype stays until an old/new BOOM failure bundle has
the same signature, failure cycle, criterion and dependency trace. Run both with
the same ELF, seed, model options and wave window under the `boom` lock. Compare
source statements, cycles and dependency edges after normalizing generated IDs
and checkout paths. Record the measured result in the PR before removal.

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

## Limit ownership

Persistent simulation: [#14](https://github.com/riscPrint/risc-v-workstation/issues/14). Build/run performance: [#74](https://github.com/riscPrint/risc-v-workstation/issues/74). Dependency-model parity: [#68](https://github.com/riscPrint/risc-v-workstation/issues/68). Backend capabilities: [#116](https://github.com/riscPrint/risc-v-workstation/issues/116). Interrupt regression: [#47](https://github.com/riscPrint/risc-v-workstation/issues/47).

Retained limit: Unattributed concurrent failures and direct JVM identity remain inconclusive. Small-only BOOM qualification does not qualify other presets. Abandoned threads live until JVM exit. Unsupported external dependencies still refuse identity.
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
