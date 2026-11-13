# Agent playbook: architecture models

Use this playbook from a core's own repository. Keep the workstation installed
in a separate repository. Keep the description and all core tuning with the
core. Read [AGENT_SETUP.md](AGENT_SETUP.md) for the C1 adapter and project setup.
Read [Arch/README.md](../Arch/README.md) and
[contract C9](contracts/c9-arch-models.md) for the model
and report limits.

For optional SoC topology, declared memory observations, and bounded model-only
sweeps, use the matching sections of [Arch/README.md](../Arch/README.md).
SoC descriptions cannot use this playbook's fixed-latency C1 calibration.
The sweep frontier covers speed only; area, power and uncertainty stay unknown.

gem5 shows trends. RTL is the truth. A report measures a model gap. It does not
give a correctness result, a C4 gate verdict, or complete C8 evidence.

Run each command block in order. Replace `/path/to/...` and example names with
verified project values. Check each command's exit status before you continue.
For `rvw arch`, exit 0 means that the command produced its result. Invalid
inputs, failed runs and comparison mismatches exit 2. With `--json`, these
failures print one object with an `error` field. Never treat that object as a
successful report.

## 1. Check the supported core type

Read the core's configuration and its top-level construction code.

```sh
cd /path/to/my-core
git rev-parse --show-toplevel
rg --files -g '*.scala' -g 'rvw.toml' -g '*Config*' -g '*Param*'
rg -n -i 'xlen|rv32|rv64|out.of.order|reorder|rename|isa|plugins' src
```

**Success check:** The source defines one supported hart. RV64 out-of-order
cores use `kind = "o3"` with `rv64gc` or `rv64gc_zba_zbb_zbs` and ABI lp64d.
RV32IM in-order cores use `kind = "minor"` or `kind = "timing"` and ABI ilp32.
Other CPU/ISA pairs are refused. Record the preset and source locations.

The VexRiscv example has uncached RV32IM descriptions and live C1 retirement
counters. Start with [its architecture guide](../examples/vexriscv/rvw/arch/README.md).
Minor and TimingSimple are explicit approximations. They do not reproduce
VexRiscv pipeline timing. Static compatibility remains separate from native
runs and calibration. Use the O3 field mapping below only for O3 models.

## 2. Select the installed workstation and core project

```sh
export RVW_HOME=/path/to/risc-v-workstation
source "$RVW_HOME/env.sh"
export RVW_PROJECT=/path/to/my-core/rvw.toml
cd /path/to/my-core
test -f "$RVW_PROJECT"
rvw --help
rvw --project "$RVW_PROJECT" regress list --json
```

**Success check:** The file exists. Both `rvw` commands exit 0. The regression
list names the intended core and presets. The project has a C1 adapter and a
shared lock for that core. The preset used below must be in `core.configs`, or
it must equal `core.default_config` when that list is empty.

**Failure action:** Use [AGENT_SETUP.md](AGENT_SETUP.md) to finish installation
or C1 setup. Fix a wrong selected file before you continue. Do not add `--core
boom` to bypass a project error. Ask the core owner which presets to support
if the source does not define a clear selection.

## 3. Check and install native tools

Check the requested tool groups. A plain `--check` does not select gem5.

```sh
"$RVW_HOME/scripts/install.sh" --with-gem5 --with-riscv-gcc --with-sim --check
```

To reuse an existing native binary, set its absolute path before the check:

```sh
export RVW_GEM5=/absolute/path/to/gem5.opt
"$RVW_HOME/scripts/install.sh" --with-gem5 --with-riscv-gcc --with-sim --check
```

If tools are missing, inspect the install actions:

```sh
"$RVW_HOME/scripts/install.sh" --with-gem5 --with-riscv-gcc --with-sim --dry-run
```

Ask the user before system package commands unless the user has already
approved them. After approval, install the missing tools:

```sh
"$RVW_HOME/scripts/install.sh" --with-gem5 --with-riscv-gcc --with-sim
source "$RVW_HOME/env.sh"
"$RVW_HOME/scripts/install.sh" --with-gem5 --with-riscv-gcc --with-sim --check
```

**Success check:** The final check exits 0. It prints `PRESENT gem5:
25.1.0.1 (RISC-V)` and reports the other requested tools as present. The native
GCC has newlib and supports the chosen ISA. Set `RVW_RISCV_CC` to an absolute
GCC executable path if the default `riscv64-unknown-elf-gcc` is unsuitable.

**Failure action:** Inspect `MISSING`, `UNUSABLE` and `WRONG VERSION` messages.
Replace or repair an invalid `RVW_GEM5` selection. To use the installer-managed
binary instead, run `unset RVW_GEM5` before installation. Source `env.sh` again
after installation. Do not substitute a Linux cross compiler or picolibc.
The benchmark build in step 7 checks the required runtime and link support.

The installer pins gem5 v25.1.0.1 at commit
`c8222cc67a399bfc01e8658dd14b30d5bfd634f9`. It builds with two jobs under the
`gem5` lock. Wait for the install to finish. No container is required.

## 4. Find the RTL parameters for the selected preset

Start with the Scala code that constructs the top level. Follow its parameter
objects and plugin configuration. Use the final preset values, including
overrides. Do not copy the default values from a parameter class without
checking its caller.

```sh
rg -n -i 'fetch|decode|rename|dispatch|commit|issue|rob|phys|ldq|stq|lq|sq' src
rg -n -i 'cache|mshr|tlb|tage|btb|ras|predict|history|latency|pipeline' src
```

If the project already has a database for this exact preset, use it to check
the structure. Set `ARCH_PRESET` to the supported C1 preset found in step 2.
Do not build a database just to obtain a parameter that is clear in Scala.

```sh
export ARCH_PRESET=your-preset
rvw --project "$RVW_PROJECT" query info --json
rvw --project "$RVW_PROJECT" query hierarchy --depth 3 --json
rvw --project "$RVW_PROJECT" query search 'rob|issue|cache|tlb' --regex --json
```

Use an exact path returned by `search` to find its Scala declaration:

```sh
export ARCH_SIGNAL='exact.signal.path.from.search'
rvw --project "$RVW_PROJECT" query where "$ARCH_SIGNAL" --json
rvw --project "$RVW_PROJECT" query drivers "$ARCH_SIGNAL" --json
```

If database extraction is needed, use the core-owned query launcher after its
setup is complete:

```sh
rvw --project "$RVW_PROJECT" query build --config "$ARCH_PRESET" --json
```

**Success check:** Source searches return the selected preset and the relevant
structures. Queries exit 0 and identify the intended design. Check JSON status
and `db_warnings` as well as the exit code. Each mapped value has a source
path, line, unit and derivation. A database helps locate elaborated signals and
storage. It does not supply an automatic gem5 parameter mapping.

**Failure action:** Read the Scala directly if no database is available. Treat
empty or truncated searches as incomplete evidence. Narrow the query or raise
`--limit`. Resolve ambiguous paths with a full path. Rebuild a stale database
through the project's launcher if needed. Do not use `status: "inconclusive"`
or a changed source location as confirmed evidence. Ask the core owner about
an unresolved parameter or timing rule.

## 5. Write the project-owned description

Use the complete example as a format template. Its numbers belong to BOOM.
Replace them with the values found in step 4.

```sh
mkdir -p rvw/arch
test ! -e rvw/arch/baseline.json
cp "$RVW_HOME/examples/boom/arch/large.json" rvw/arch/baseline.json
"${EDITOR:-vi}" rvw/arch/baseline.json
"${EDITOR:-vi}" rvw.toml
```

Stop before `cp` if `test` reports an existing description. Review that file
instead. Add or edit one `[arch]` table in `rvw.toml`:

```toml
[arch]
description = "rvw/arch/baseline.json"
sources = "/path/to/riscv-tests/benchmarks"
benchmarks = "rvw/out/arch/bench"
```

All three paths resolve against the directory of `rvw.toml`. Obtain the
riscv-tests source checkout separately. The build does not download it.
Record the checkout revision with the core's experiment notes.

Use this mapping. Field names are gem5 names, not required Scala names.
The Scala column identifies where to look in an arbitrary Spinal core.

| Description field | RTL meaning and Spinal source to inspect |
|---|---|
| `schema`, `kind` | Use `rvw.arch-core/1` and `o3`. Step 1 must establish the supported core type. |
| `config`, `isa` | Use the C1 preset name and one supported ISA string. Check the top-level constructor, decoder configuration, CSR configuration and enabled execution units. |
| `cpu.fetchWidth` | Instructions fetched per cycle in the model. Inspect fetch packet construction and instruction alignment. Convert byte or bit widths to instruction throughput with an explicit assumption for compressed instructions. |
| `cpu.fetchBufferSize`, `fetchQueueSize`, `numFTQEntries` | Model fetch buffering and fetch-target queue capacity. Inspect front-end FIFOs, `StreamFifo` depth, `Vec` size and FTQ parameters. Record whether each RTL capacity counts bytes, packets or instructions. These structures can differ from gem5. |
| `cpu.decodeWidth`, `renameWidth`, `dispatchWidth`, `commitWidth` | Instructions per cycle at each stage. Inspect lane counts, `Vec` lengths, enqueue/dequeue ports and the preset width parameters. |
| `cpu.squashWidth` | Model recovery bandwidth. Inspect ROB rollback and flush logic. A bulk RTL flush does not directly define a gem5 squash width. Mark an approximation. |
| `cpu.issueWidth`, `wbWidth` | Total model issue and writeback widths. Inspect scheduler grants, execution lanes, arbitration and writeback ports. Do not count units that cannot issue at the same time as independent bandwidth. |
| `cpu.fetchToDecodeDelay`, `decodeToRenameDelay`, `renameToIEWDelay`, `issueToExecuteDelay`, `iewToCommitDelay` | Forward stage delays in cycles. Follow `Reg`, `RegNext`, pipeline stages and ready/valid boundaries in the selected design. Match gem5 stage boundaries explicitly. Stalls are not fixed pipeline delays. |
| `cpu.iewToFetchDelay`, `commitToFetchDelay` | Feedback delays in cycles. Follow branch resolution, redirect and commit recovery paths to fetch. Document boundary differences. |
| `cpu.numROBEntries` | Total ROB instruction capacity. Inspect allocation and storage dimensions. Multiply rows by banks or lanes only when all entries hold separate instructions. |
| `cpu.numPhysIntRegs`, `numPhysFloatRegs` | Physical register counts. Inspect rename maps, free lists and register-file storage depth. Count total physical registers, not just free registers. |
| `cpu.LQEntries`, `SQEntries` | Load and store queue capacities. Inspect LSU parameter objects, queue arrays and allocation rules. |
| `cpu.cacheLoadPorts`, `cacheStorePorts` | Model data-cache access limits. Inspect LSU request arbitration and actual cache acceptance capacity. Functional-unit count alone is not sufficient. |
| `queues[].entries` | Entries in each gem5 issue queue. Inspect scheduler storage and the instructions each RTL queue can accept. |
| `queues[].units[].ops`, `count` | gem5 operation classes and unit instances. Trace decoder operation selection to each scheduler and execution unit. Match classes explicitly. Confirm shared-unit arbitration. Separate FU descriptors can create independent model resources. |
| `queues[].units[].latency`, `pipelined` | Fixed operation latency in cycles and whether the model unit accepts pipelined operations. Inspect multiplier stages, divider control and FP units. Variable latency or an initiation interval greater than one needs an explicit approximation. |
| `predictor.tage.nHistoryTables`, `minHist`, `maxHist` | Number of tagged tables and history bounds. Inspect the predictor constructor and history-length list. gem5's history schedule can differ from the RTL list. |
| `predictor.tage.tagTableTagWidths`, `logTagTableSizes` | Tag widths and base-2 logs of table entry counts. Inspect predictor memory dimensions. Both arrays need `nHistoryTables + 1` values. Index 0 is the base table. Its tag width must be 0. |
| `predictor.tage.logUResetPeriod` | Base-2 log of the model usefulness reset period. Inspect RTL usefulness ageing logic and its counter. Record semantic differences. |
| `predictor.loop.logSizeLoopPred`, `logLoopTableAssoc` | Base-2 logs of loop predictor size and associativity. Inspect loop predictor tables. The association log must not exceed the size log. |
| `predictor.btb.numEntries`, `associativity`; `ras_entries` | BTB entry count, ways and RAS depth. Inspect BTB storage/index logic and the return stack. BTB entries must be divisible by associativity. |
| `icache.size`, `dcache.size`, `assoc` | Cache capacity in bytes and ways. Inspect cache parameter objects and tag/data `Mem` dimensions. Compute bytes as sets times ways times line bytes. |
| Cache `tag_latency`, `data_latency`, `response_latency` | gem5 cache access delays in cycles. Inspect cache stages and response registers. These fields do not necessarily add to the RTL hit latency. Check effective model behavior. |
| Cache `mshrs`, `tgts_per_mshr`, `write_buffers` | Outstanding misses, requests merged per miss and write-buffer capacity. Inspect miss status entries, replay/merge logic and store/writeback buffers. The resource boundaries can differ. |
| Cache `is_read_only`, `writeback_clean` | Model cache policy. Inspect refill, store, eviction and clean-writeback logic. Use booleans. Do not infer these policies from capacity. |
| `itlb_entries`, `dtlb_entries` | Model TLB entries. Inspect MMU/TLB arrays, ways and sets. Document separate levels, superpage entries and replacement differences. |
| `line_bytes`, `bus_bytes` | Cache line size and memory bus width in bytes. Inspect cache block parameters and memory interface data widths. Divide bit widths by 8. `line_bytes` must be a positive power of two. |
| `memory_latency` | Fixed external-memory latency in whole cycles. Read the C1 memory model and its `mem_latency` handling. This is a harness setting, not a cache hit delay. The model clock is 1 GHz, so one cycle is 1 ns. |

Do not retain a template value just to complete the file. Use a core-owned note
for every approximation, omitted scalar default and unresolved mapping. Keep
these notes outside the description JSON. Unknown top-level fields are errors.
For example, use `rvw/arch/README.md` to record the source revision, source
locations, derivations, model assumptions and intended use.

The O3 model fixes these structures: one `RiscvO3CPU`, LTAGE with a loop
predictor, `SimpleBTB`, a RAS, `SimpleIndirectPredictor`, split L1 caches, and
fixed-latency memory. It has no L2. RAM is 512 MiB at `0x80000000`.
The `isa` label selects XLEN. It does not disable gem5's extra ISA extensions.

If the RTL has a different predictor, no cache or TLB, an L2, a different memory
map, variable FU timing, or another unsupported structure, do not invent a
matching field. Stop a claim of faithful mapping. Ask the core owner whether
a stated approximation is useful for the intended experiment. Otherwise stop
the experiment and report the required generic extension. Do not silently
replace an absent structure with a positive template size.

CPU and cache objects accept scalar gem5 parameters only. Unknown parameter
names, vectors and object references fail model construction. The CPU cannot
override `numThreads`, `switched_out`, `checker`, `max_insts_any_thread`,
`max_insts_all_threads` or `max_insts_any_thread_warmup`.
Queue entries, unit counts and latencies must be positive integers.
`pipelined` must be a boolean. Operation classes must be valid gem5 names and
must not be `No_OpClass`. Do not add broad fallback classes to conceal a missing
mapping. The BOOM template preserves a historical fallback that overlaps other
queues. Read [its limits](../examples/boom/README.md) before using it.

Check the selected project and description without a simulation:

```sh
"$RVW_HOME/rvw/.venv/bin/python" -B - <<'PY'
import os
from rvw.arch.core import settings
from rvw.regress.config import load_config
p, _, d = settings(project=os.environ['RVW_PROJECT'])
c = load_config(project=p.path)
assert d['config'] in (c.configs or [c.default_config]), 'unknown C1 preset'
print(p.path, p.name, d['config'], d['isa'], d['memory_latency'])
PY
```

**Success check:** The check exits 0. It prints the intended project, core,
preset, ISA and positive integer memory latency. All fields have supported
values or documented approximations approved by the core owner.

**Failure action:** Fix duplicate JSON keys, missing fields, invalid types,
unsupported ISA strings or a wrong C1 preset. The script uses the installed
parser. It does not check gem5 parameter names or operation classes. Step 8
checks those during model construction. Do not interpret parser success as
cycle accuracy.

## 6. Check the C1 adapter's benchmark support

Inspect the selected adapter and its memory model:

```sh
"${EDITOR:-vi}" "$RVW_PROJECT"
rg -n 'run-many|mem_latency|memLatency|bench_stats|roi_cycles|roi_instret|MemWords' rvw
```

Read the files named by `core.adapter` if they are outside `rvw/`.
The adapter must implement `run-many --manifest FILE --jobs 1`. It must honor
each job's preset, seed, fixed memory latency and cycle limit. It must load the
captured ELF. It must return a conclusive C1 pass with matching job identity.

Read the two 64-bit words at the ELF's `bench_stats` symbol as ROI cycles and
retired instructions. Emit them as `metrics.roi_cycles` and
`metrics.roi_instret`. Keep C1 top-level `cycles` and `instret` as whole-program
counters. The workstation supplies `riscvsim.MemWords` for byte-lane writes.
See [BoomAdapter.scala](../RiscvSim/boom/src/main/scala/riscvsim/boom/BoomAdapter.scala)
for its use. Adapt the memory interface in the core's own adapter.

**Success check:** Source inspection confirms all required behavior. Step 9
must then confirm it with actual C1 results. Calibration uses seed 1, fixed
latency from the description, one worker and `max_cycles = 50000000`.

**Failure action:** Add missing behavior to the core-owned adapter before
calibration. Do not substitute whole-program counters for missing ROI
counters. Resolve unknown memory latency semantics before comparing cycles.
Do not change workstation code to tune one core.

## 7. Build the same benchmark ELFs for both engines

```sh
rvw --project "$RVW_PROJECT" arch build --bench median,vvadd,memcpy --json
```

**Success check:** The command exits 0. It returns schema `rvw.arch-build/1`.
The configured benchmark directory contains `median.riscv`, `vvadd.riscv`,
`memcpy.riscv`, `build.log` and `build.json`. The manifest records each ELF hash,
the selected ISA and preset, and compiler and gem5 identities.
The runtime exports `tohost`, `tohost_exit`, `setStats` and `bench_stats`.
It stores ROI counters at `bench_stats` and removes console HTIF traffic.

**Failure action:** Read `build.log` in `arch.benchmarks`. Fix the source path
if `common/syscalls.c` or a selected benchmark is missing. Supply native newlib
GCC if the link fails. If the runtime patch refuses changed source text, review
the source version and patch requirements. Do not remove the guard to force a
build. Empty, duplicate or malformed benchmark selections are errors.

Without `--bench`, all nine default benchmarks are selected: `median`, `qsort`,
`rsort`, `towers`, `vvadd`, `memcpy`, `multiply`, `dhrystone` and `spmv`.
Use the same selection in the later commands. Rebuild and rerun both engines
after a compiler, source, ISA or compiler-flag change.

## 8. Run a model-only check

Choose an output directory that does not exist:

```sh
rvw --project "$RVW_PROJECT" arch run --bench median,vvadd,memcpy \
  --out rvw/out/arch/model-1 --timeout 600 --json
```

**Success check:** The command exits 0. The output contains `inputs/`,
`inputs.json` and `gem5.json`. Each benchmark row has `status: "pass"` and
positive ROI `cycles` and `instret`. The per-benchmark directory
`gem5/NAME/` contains `run.log`, `bare.json`, `config.json` and gem5 statistics.
Check `config.json` for effective CPU and cache values, including defaults.
`bare.json` must report `tohost: 1`, `exit_code: 0`, `roi: "setStats"` and
positive `bench_stats` counters. Exactly two `setStats` entries must occur.

**Failure action:** Use a fresh output path if the directory exists. Read
`gem5/NAME/run.log` and `bare.json` for unknown parameters, bad operation
classes, unsupported object construction, missing ELF symbols or guest failure.
The ELF must be a little-endian RV64 executable with load segments inside the
fixed RAM range. A tick limit or incomplete exit is a failure. A wall timeout
is also a failure. Diagnose it before raising `--timeout` and retry in a new
directory. Do not edit a failed result into a pass.

## 9. Run RTL calibration

```sh
rvw --project "$RVW_PROJECT" arch calibrate --bench median,vvadd,memcpy \
  --out rvw/out/arch/calibration-1 --timeout 3600 --json
```

The command captures each ELF once. Both engines use those copied bytes.
It runs RTL under the project's lock. It runs gem5 serially under the `gem5`
lock. Do not start another copy to bypass a lock. Wait for the command to end.
The timeout bounds the C1 batch and each gem5 process. It does not change the
fixed RTL job cycle limit or the model tick limit.

**Success check:** The command exits 0. The output contains `rtl.json`,
`gem5.json`, `calibration.json` and `summary.txt`. The report schema is
`rvw.arch-compare/1` and its status is `reported`. Each RTL result in
`rtl/NAME/result.json` is a conclusive pass. Its ELF hash, core, preset, seed 1
and memory latency match the job. Each engine has positive ROI counters.
The benchmark IDs, ELF hashes and ROI instruction counts match between engines.

**Failure action:** Read `rtl/run.log`, `rtl/jobs.jsonl` and each C1 result
for build failures, assertions, traps, cycle limits or identity mismatches.
Read the gem5 logs if RTL passed. Fix the adapter if ROI metrics are absent.
Investigate unequal instruction counts as an invalid comparison. Check the
runtime, CSR counter semantics, traps and ROI boundaries. Do not adjust cycle
parameters to hide that mismatch. If a manifest hash is stale, rebuild the
ELFs and rerun both engines. Use a new output directory after any failed run.

## 10. Recheck the evidence and interpret the gap

```sh
rvw --project "$RVW_PROJECT" arch compare \
  rvw/out/arch/calibration-1/rtl.json \
  rvw/out/arch/calibration-1/gem5.json --json
cat rvw/out/arch/calibration-1/summary.txt
```

**Success check:** `compare` exits 0 and reports `status: "reported"`.
It rechecks the saved ELF bytes, raw evidence hashes and counters. Preserve
the output tree at its recorded absolute paths.

Read each row with RTL as the base:

- `base_ipc` is RTL ROI instructions divided by RTL ROI cycles.
- `candidate_ipc` is gem5 ROI instructions divided by gem5 ROI cycles.
- `ipc_ratio` is gem5 IPC divided by RTL IPC. With equal instruction counts,
  it is also RTL cycles divided by gem5 cycles. Above 1 means gem5 is faster.
- `cycle_gap_percent` is `100 * (gem5_cycles / rtl_cycles - 1)`.
  Positive means gem5 is slower.
- `geomean_ipc_ratio` combines the per-benchmark IPC ratios. Read individual
  rows too. Opposite errors can hide behind an aggregate near 1.

Equal ROI instruction counts are a validity check. They do not prove equal
instruction streams, correct execution or accurate timing. `reported` does
not mean that calibration was accepted. This tool does not fit parameters or
apply an acceptance threshold.

**Failure action:** Missing files, changed evidence, different benchmark sets,
unequal hashes or unequal ROI instruction counts invalidate the comparison.
Restore the original evidence or rerun both engines. Do not edit report hashes
or counters to make comparison succeed.

For a valid report with a large gap, inspect per-benchmark behavior. Check
widths, queue placement, FU sharing, predictor assumptions, cache timing,
memory latency and compiler layout. Short ROIs are sensitive to initial cache
and predictor state. Stop using the model for a decision when its observed
error or unmodeled mechanism can change that decision. There is no universal
percentage that makes every model trustworthy. Ask the core owner to set a
tolerance for the intended use and workload set. Record that choice before
claiming the model is adequate. Test it on workloads outside any tuning set.
Confirm every claimed performance gain in RTL.

## 11. Keep tuning and experiment records in the core project

Make a separate description for each candidate. Keep the baseline evidence.

```sh
test ! -e rvw/arch/candidate-1.json
cp rvw/arch/baseline.json rvw/arch/candidate-1.json
"${EDITOR:-vi}" rvw/arch/candidate-1.json
"${EDITOR:-vi}" rvw.toml
```

Stop before `cp` if the candidate file exists. Set `[arch].description` to
`rvw/arch/candidate-1.json`. Check it with step 5's parser command. Run the
candidate with a new output directory:

```sh
rvw --project "$RVW_PROJECT" arch calibrate --bench median,vvadd,memcpy \
  --out rvw/out/arch/calibration-candidate-1 --timeout 3600 --json
git diff -- rvw.toml rvw/arch
git status --short
```

**Success check:** The candidate produces valid comparison evidence as in
steps 9 and 10. The core's files record the parameter change, source evidence,
model gap, workload set and intended use. The diff contains only intended
project changes. Use a matching RTL preset when testing an RTL change.
Use separate records for hypothetical model sweeps and measured RTL changes.

**Failure action:** Do not use a valid baseline result to excuse invalid
candidate evidence. Do not change generic workstation defaults, add core
preset switches to `Arch/model.py`, or conceal a gap with a fallback unit.
Keep a fitting experiment in the core project. Propose a generic extension
only when the runner needs a new modeling capability.

The shipped BOOM project's `RVW_ARCH_CONFIG` override comes from its own TOML
data. It is not an automatic description selector for every core project.

For VexRiscv RV32IM, use the project-owned Minor or TimingSimple description.
Check both engines before using a fitted candidate.

## Source and validation limits

This workflow follows these installed sources:

- [Arch/README.md](../Arch/README.md) and [C9](contracts/c9-arch-models.md).
- [Arch/model.py](../Arch/model.py): description parser, fixed topology,
  gem5 object construction, ELF checks and ROI/exit checks.
- [arch/core.py](../rvw/src/rvw/arch/core.py) and
  [arch/cli.py](../rvw/src/rvw/arch/cli.py): project selection, benchmark build,
  run capture, calibration, comparison and exit codes.
- [Arch/bench/Makefile](../Arch/bench/Makefile) and
  [runtime patch](../Arch/bench/rt/patch_syscalls.sh): compiler flags and ROI runtime.
- [BOOM project data](../examples/boom/) and
  [VexRiscv configuration](../examples/vexriscv/rvw/src/main/scala/rvwvex/VexTop.scala).
- [query/cli.py](../rvw/src/rvw/query/cli.py) and
  [SpinalDB/README.md](../SpinalDB/README.md): database navigation and source limits.

The parameter table is a guide for source inspection. It is not an extraction
tool or a verified mapping for every Spinal core. The core owner must review
approximations and the intended model use. Reports keep local evidence and
absolute paths. They do not claim complete C8 capture or immutable generations.
Inputs and tools must stay stable during commands. File races and hostile
inputs are outside the stated threat model. Simulator reports do not prove
hardware behavior.

## Limit ownership

Fitting: [#12](https://github.com/riscPrint/risc-v-workstation/issues/12). RV32/in-order support: [#13](https://github.com/riscPrint/risc-v-workstation/issues/13). Wide-core structures: [#72](https://github.com/riscPrint/risc-v-workstation/issues/72). Experiment management: [#160](https://github.com/riscPrint/risc-v-workstation/issues/160).

Retained limit: Source-to-model parameter mapping remains manual and reviewed. Complete capture, portable report paths and immutable generations have no dedicated issue. C9 remains measured model evidence, with no calibration acceptance or hardware proof.

For generic automatic fitting, use the search plan in
[Arch/README.md](../Arch/README.md#bayesian-fitting-repeats-and-predictions).
Keep plans, descriptions and results in the core project. Search uses saved
RTL observations, selects settings on training events, and scores the selected
settings on held-out workloads. Do not use the held-out score for more tuning
without a new independent held-out set. Use `arch measure` to repeat both
engines. Use `arch predict` before a later RTL experiment, then use
`arch score-prediction` to record its model gap. Report intervals and event
correlations with their limits. Neither supplies a fidelity verdict.
