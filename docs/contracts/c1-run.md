# C1. Run contract (core adapter)

RiscvSim supports the optional `--spinaltrace` model flag on `build`, `run`,
`run-many` and `identity`. Its model identity includes `spinaltrace` (default
false), and replay preserves it. A supported traced model emits a `pdg` artifact
from its RTL elaboration. `--wave` records the instrumented wave. A missing
requested trace model is an error; it must not yield computed-cause claims.

Each core provides one adapter command. BOOM's is `RiscvSim/boom/run.sh`.

```
<adapter> build --config NAME [--rvfi] [--wave] [--coverage] [--konata] [--json]
<adapter> run   --elf PATH --out DIR [--config NAME] [--seed N] [--max-cycles N] [--mem-latency N]
                [--rvfi-trace] [--wave [--wave-from CYCLE] [--wave-to CYCLE]] [--konata] [--coverage]
<adapter> run-many --manifest jobs.jsonl [--jobs N]   # one JVM, one compiled model, many ELFs
<adapter> identity                                     # optional: what results depend on (see below)
```

`run-many` takes one JSON object per line with the same keys as `run`'s options (`elf`, `out`,
`config`, `seed`, ...), written with underscores or dashes (`max_cycles` or `max-cycles`). A missing seed means "pick one and record it". `--mem-latency` absent means
randomized memory timing; present means fixed latency.

Optional `--irq-schedule '1:0x0,1000:0x80,12000:0x0'` (manifest
`irq_schedule`, a string) selects full input levels in `mip` bit positions.
Cycles must strictly increase, start at 1, and finish before `max_cycles`.
Adapters reject unsupported input bits. A selected schedule replaces software device
levels. Without a schedule, existing device behavior stays active. At sampled edge N,
the adapter drives the new levels for the next edge. C2 records the actual driven
levels at N. Interrupt acceptance at N is not evidence for the new levels.
C1 `irq_schedule` stores the normalized string, or null. Replay carries the same string.
The schedule is inline, so replay needs no separate stimulus file.

Optional, declared in the core config of `rvw regress` (`[core] identity = true`, `wall_timeout = true`):

- `identity` prints text that changes whenever anything besides the ELF and the run options can
  change a result (toolchain versions, adapter and core source keys). `rvw regress` adds its hash
  to the result cache and resume keys; if it fails, nothing is reused.
- `wall_timeout` (manifest key; `run --wall-timeout S`): a wall-clock limit in seconds per run.
  The adapter ends the run as `timeout` with `"wall_clock_timeout": true`, so a hung test does
  not hold the batch. It writes that result within max(2 s, 10%) of the limit (RiscvSim abandons
  a simulation that does not stop); `rvw regress` stops a batch only after `wall_timeout` + 10 s +
  20% without a new result.

`run` writes `DIR/result.json`:

```json
{
  "schema": "rvw.run/1",
  "core": "boom", "config": "small",
  "elf": "/abs/path/rv64ui-p-add", "elf_sha256": "…", "rtl_sha256": "…",
  "seed": 12345, "max_cycles": 200000, "mem_latency": null,
  "status": "pass | fail | timeout | assert | rvfi_error | error",
  "fail_code": null,
  "message": "assertion text, exception message, or null",
  "cycles": 1234, "instret": 456,
  "wall_s": 3.2,
  "source": {"core_repo": "/abs/path", "core_rev": "<short commit>", "core_dirty": false,
             "core_rev_full": "<full commit>",
             "tools_repo": "/abs/path", "tools_rev": "<full commit>", "tools_dirty": false},
  "tools": {"verilator": "5.049", "spinalhdl": "1.15.0"},
  "artifacts": {"log": "run.log", "rvfi_trace": "rvfi.jsonl", "wave": "wave.vcd",
                "konata": "konata.log", "coverage": "coverage.dat"},
  "replay": "RiscvSim/boom/run.sh run --elf … --seed 12345 --config small --out …"
}
```

`elf_sha256` identifies the bytes loaded by this run. RiscvSim reads the ELF once before
model compilation and passes the captured input as `RunContext.elf`. Adapters use that input
for loading, symbols and disassembly. They must not reopen the original `elf` path. That path
remains metadata and the input path for a later replay; a replay needs the same ELF bytes to
reproduce the run.

RiscvSim also records optional `tools.native_build`: the native cache namespace and SHA-256,
effective native environment values, an inherited environment digest and its ignored keys, tool paths,
executable hashes and full versions, and `cache_enabled` with `cache_disabled_reasons`.
The launcher records these values once before compilation. `identity` uses the same collector
as model compilation. An unknown native input disables caching and result reuse. Replay restores
the saved native environment and unsets absent values. It uses the current launcher's make wrapper.
Replay needs the same installed tools and input bytes.

Optional `"metrics"`: an object of named numbers measured by the run. Programs that store
region-of-interest counters to a `bench_stats` symbol (two 64-bit words: cycles, then instret, as
riscv-tests benchmarks do) report them as `metrics.roi_cycles` and `metrics.roi_instret`; `cycles`
and `instret` stay whole-program. `rvw regress` uses the ROI values for benchmark performance.

`result.json` appears atomically (written elsewhere and renamed). `"wall_clock_timeout": true`
marks a `timeout` of the wall clock, not of `max_cycles`: it says nothing about the core.
Optional `"inconclusive": "<reason>"` marks a result the adapter cannot vouch for, e.g. a failure
it could not attribute to this run (RiscvSim: an `assert` printed while other simulations ran,
pending or failing its serial rerun; RiscvSim's `details.serial_rerun.attributed: false` and a
`details.concurrent` `assert`/`rvfi_error` without `serial_rerun` are read the same way).
Debug reruns also require the returned `elf_sha256` to match the requested ELF bytes.
A missing or different hash makes the attempt inconclusive.
Debug reruns check each explicitly requested C1 seed, config, max_cycles and mem_latency
against the returned result. A missing or different value marks the attempt inconclusive.
It cannot reproduce or rule out the requested failure.
A C1 result is evidence about the core only when `rvw.results.inconclusive_cause` finds nothing:
not `inconclusive`, not status `error` (the harness could not run the test), not `synthesized`
(rvw wrote it), not a wall-clock timeout. Every reader uses that one rule (regress resume, cache
and compare; reduce, bisect and bundle): such a result neither reproduces nor rules out a failure.
The BOOM launcher records full source commit IDs and dirty flags at start. `rtl_sha256`
identifies its generated Verilog, including enabled probes and the RVFI monitor. The harness
identity is `source.tools_rev` plus `source.tools_dirty`. The native identity is
`tools.native_build.sha256`. Direct JVM launches lack the launcher's native binding and remain
inconclusive. The replay path is relative to the tools checkout.

Artifact paths are relative to `DIR`; absent artifacts are omitted. `status` meanings: `fail` the
program wrote an odd value other than 1 to `tohost` (`fail_code` is the value >> 1); `assert` an
HDL assertion or simulation exception; `rvfi_error` the riscv-formal monitor flagged an error;
`error` the harness itself failed (bad ELF, build failure).

C1 `run` and `run-many` exit 2 for `status: error`, including input errors before
model compilation. This takes priority over missing-evidence markers such as missing RTL.
Otherwise they exit 3 for an explicit `inconclusive` marker, 0 when all runs pass,
and 1 for other run failures. Error results remain unsuitable as core evidence.

Optional `run-many --persistent --jobs 1` uses the serial fresh-instance server.
Adapters must declare fresh native and harness state for each request. C1
`execution_mode` is `server`; `details.simulation_session` records session UUID,
model run number and reset policy. RTL and native hashes still identify the model.
An abandoned worker stops the batch before later requests and forces exit 2,
including when no result exists for those requests. This is model reuse, not
result reuse. Regression `[core] persistent = true` selects this mode and skips
the separate pre-build process. Each process has a serial timeout budget.
Regression can start several isolated processes.

Cosim reproduction metadata records `tools.spike_build.spike_identity` with the
installed reference's version, source revision when supplied, and origin. The same
label is bound into `build_inputs`. Source installs supply `share/rvw/spike-source.json`;
Homebrew builds capture their receipt and available SBOM. An unlabelled external
build has null version/revision. These labels are package provenance, not binary
attestation. The captured library and shim hashes identify the executed bytes.
C1 from an RTL-only run does not imply that Spike ran.

### Native checkpoint envelope (`rvw.native-checkpoint/1`)

This adapter API format is distinct from from-reset replay descriptors and
portable architectural checkpoints. No bundled adapter currently provides the
required live native port.

The JSON envelope contains `payload` and `sha256`. The digest covers UTF-8 JSON
of the payload with sorted keys, compact separators and no non-finite numbers.
The payload contains `schema`, `identity`, `state` and `native`. `native` is
nonempty strict base64. `identity` contains exactly four lowercase SHA-256
fields: `rtl`, `native_build`, `harness`, `stimulus`. All must equal the expected
restoring instance identities.

`state` contains exactly `scheduler`, `clock`, `memory`, `pending`, `rng`,
`devices`, `interrupts`, `monitors`, `rvfi`, `stimulus` and `counters`. Each adapter defines
and validates its component representations. All components must be present
and non-null. Empty inventories must be explicit. The native build and harness
identities bind these representations to their implementation.

Save and restore require a stopped quiescent instance and an empty external
effects inventory. Validate bytes, identity and adapter state before mutation.
Discard an instance after a failed restore. A restored snapshot is not an
equivalence verdict. Qualification needs a fresh-process native restore and
complete C2 suffix and terminal-counter comparison with uninterrupted execution.
