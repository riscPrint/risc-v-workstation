# rvw bundle, rvw reduce, rvw bisect

Failure debugging for any core that follows the run contract (C1) and the RVFI trace (C2). They
replace the step where a human opens a waveform viewer and tells the agent where to look
(commercial reference: Verdi's debug apps). Everything core-specific (signal names, unit names,
state encodings) lives in the core's debug description, `RiscvSim/<core>/debug.toml`; BOOM's is
[`RiscvSim/boom/debug.toml`](../../../../RiscvSim/boom/debug.toml).

```sh
rvw bundle  RUN_DIR [--out DIR] [-n 64] [--cut-cycles 500] [--rerun-window 3000] [--konata] [--no-rerun]
rvw reduce  RUN_DIR [--modes cycles,seeds,latency] [--seeds 12] [--latencies 1,2,5,10,20,50] [--symbol NAME]
rvw bisect  RUN_DIR --good REV [--bad REV] [--core-repo PATH] [--core-env SPINAL_BOOM]
```

All three take `--json`: stdout is then exactly one JSON document, or empty on an error (exit 2).
Progress lines (`[bundle] ...`, `[reduce] ...`, `[bisect] ...`) and git's own output go to stderr.
Heavy re-runs hold the machine-wide core lock (the one `scripts/with-lock.sh
<core>` takes; set `RVW_NO_LOCK=1` to skip it for cheap cores and tests). rvw takes the lock before
it starts the adapter, so `--timeout` counts only the run, never the wait in the lock queue; the wait
is reported (`lock_wait_s` in reduce trials and bisect steps, a line in the attempt's log).

## rvw bundle (contract C5)

Input: a C1 run directory (`result.json`, optionally `rvfi.jsonl`, `wave.vcd`, `konata.log`).
Output (default `RUN_DIR/bundle/`):

| File | What |
|---|---|
| `summary.md` | For an agent: status and message, run settings, suspected unit with evidence, last progress, last 16 retirements, pipeline snapshot at the failure, channel activity, in-flight instructions, dependency trace, files, next commands |
| `summary.json` | The same, structured (`rvw.bundle/1`) |
| `retired.txt` | Last N retired instructions: order, cycle, pc, word, `function: disassembly`, rd value, memory access, recent traps |
| `wave-window.vcd` | The last `--cut-cycles` cycles before the failure, self-contained (see `rvw wave cut`) |
| `dynpdg.json`, `dynpdg.txt` | SpinalTrace dynamic dependency trace of the failing assertion (when the build has a PDG) |
| `replay.sh` | Exact reproduction through the adapter, under the lock: `replay.sh [OUT_DIR]` (only the `--out` value is replaced). Omitted when both reruns and SpinalTrace are disabled. |
| `rerun/` | The re-run made for the wave and trace, when one was needed (a new directory per attempt: `rerun-2`, ... if it exists) |

What it does:

1. **Re-run when needed.** If the run has no wave covering the failure cycle, or no RVFI trace, it re-runs
   the run's `replay` command with `--wave --wave-from F-W --wave-to F+20 --rvfi-trace` (W =
   `--rerun-window`, default 3000 cycles), and checks that the re-run has the same failure signature at
   the same cycle (reported as "reproduced"). If not, the bundle says so: the failure is not
   deterministic for the seed. An inconclusive re-run (the shared rule `rvw.results.inconclusive_cause`: C1 `inconclusive`, a
   harness `error`, a synthesized result or a wall-clock timeout) is never "reproduced": the bundle records the reason (`rerun.inconclusive`) and does not use its wave,
   trace or snapshot. Each re-run writes to a new directory, so an older `result.json` is never
   read as the re-run's result, and a timeout stops the adapter's whole process tree.
2. **Last progress.** Reads `rvfi.jsonl` backwards until it has the last `-n` retirements (or reaches the
   file start, so trailing interrupt or other events never hide a retirement), disassembles
   each pc with the ELF's objdump, finds the oldest unretired instruction (`pc_next` of the last
   retirement) and classifies it (load, store, amo, fence, system, muldiv, fp, branch, alu). For
   timeouts it reports the cycles since the last retirement, or a spin loop (smallest set of pcs the
   recent retirements keep revisiting).
3. **Pipeline snapshot** at the failure cycle from the wave cut (if the wave does not reach the failure,
   the snapshot is at the end of the wave and the summary says so in bold), driven by `[[snapshot]]` groups: single
   values with enum labels, counts of valid bits, busy counts, and per-entry tables (e.g. one row per
   live load-queue entry with its pc, ROB index and state bits).
4. **Channel activity** over the window from `[handshakes]`: fires per valid/ready channel, cycles since
   the last fire, channels stuck with valid and no ready, requests (by channel and id) without a
   response. With opcode signals and `[handshakes.closes]`, a response closes only the request type it
   answers (a TileLink ReleaseAck cannot close an A Get with the same source).
5. **Konata in-flight list** when a Konata log exists (`--konata` asks the re-run for one). Read with
   `rvw.perf.kanata` (`.gz` logs too); label type 0 is shown, label type 1 (hover text) as detail.
6. **SpinalTrace** `dyn-pdg` with criterion `line:<File>:<line>` of the assertion, when the run has a
   `pdg` artifact (a SpinalTrace-instrumented build) or `[spinaltrace].pdg` points to one, and
   `spinaltrace-cli` is on `PATH`, in `SPINALTRACE_CLI`, or built in `SpinalTrace/target/release`.
   With `[spinaltrace].adapter` and no PDG, the bundle re-runs through that adapter; it uses the
   re-run's PDG and wave only if the re-run is conclusive and fails with the same signature at the same
   cycle (`rerun_spinaltrace.reproduced`).
7. **Digest of the trace**: the source statements nearest the traced value (breadth-first over the
   dependency edges), with their values and modules, so the reader sees the causal chain directly. Rows
   are ordered by content, so the same graph gives the same digest whatever the order in `dynpdg.json`.
8. **Suspected unit**: assertion file → unit (`[failure].units`); for hangs, class of the oldest
   unretired instruction → unit (`[failure].insn_units`); plus evidence from the channels.

### Wave time and cycles

Cycle N is at wave time `time_of_cycle_1 + (N - 1) × period`. Both come from the run's `details`
(`wave_time_of_cycle_1`, `wave_time_per_cycle`); BOOM's cycle 1 is about 16 cycles into the wave, after
reset. The period falls back to `[core].period` or the clock. Without `wave_time_of_cycle_1` the
mapping is unknown: the bundle does not trust the wave to reach the failure (it re-runs), and if it must
use the wave anyway it says that its cycle labels assume cycle N at N × period. A wave covers the failure
only if `details.wave_window` (when present) includes the failure cycle and the wave reaches the failure
cycle's time. `summary.json` records the mapping as `clock`.

### RVFI stamps and the wave

The RVFI trace stamps a retirement some cycles after the commit is visible in the wave. With
`[core].commit` (a regex for the commit-valid signals) the bundle measures this skew: it compares the
per-cycle retirement counts of the RVFI tail with the per-cycle commit counts in the wave for shifts
-8..8 and reports the shift that matches (at least 90% agreement, no tie), as `rvfi_skew`. Measured on
BOOM `large` (qsort, the demonstration below): **2 cycles**, agreement 1.0 over 22 cycles (last
retirement stamped 50,075, committed in the wave at 50,073). `retired.txt` keeps the RVFI stamps;
subtract the skew to find a retirement in the wave.

### SpinalTrace on BOOM

Measured on BOOM `small` (0cb0b69) with the fixes in this branch (probe names from files with `-`,
two `conversion.rs` crashes, HGLDD Vec ordering). Since 2026-10-21, `conversion.rs` rewires edges into
probe vertices to the probes' sources instead of dropping them, and `dyn-pdg --summary` prints how many
had no source; the costs below were measured before that change.

| Step | Cost |
|---|---|
| Instrumented elaboration + `pdg.json` (`SpinalTraceSim.compile`) | 50 s, PDG 197 MB |
| `dyn-pdg` on the whole 2,500-cycle wave | 8 min, 34 GB peak, then a crash (since fixed) |
| `dyn-pdg` on a 20-cycle window (what the bundle does) | 5 s, 0.9 GB, ~40k dynamic vertices |

So the trace must run on a short window, which is what `--trace-cycles` does. The trace needs a wave
of the *instrumented* model (the naming phase keeps the probe wires; the plain build's wave lacks
them). The bundle requests `--spinaltrace` from the run adapter when no graph is
available. RiscvSim records the flag in model identity and copies the graph to
the run's `pdg` artifact. The trace uses the re-run only if it reproduces the
same failure at the same cycle with conclusive evidence. Missing model support
or a missing graph skips the trace. It cannot produce a cause digest.
The optional `[spinaltrace].adapter` override supports older adapters.
The BOOM prototype stays until old/new failure-bundle dependency traces match;
see [RiscvSim](../../../../RiscvSim/README.md#dependency-trace-model).

## rvw reduce

Shrinks a failure while keeping its signature (the shared C3 signature from `rvw.results`, e.g.
`assert:lsu.scala:1241`; `--signature re:REGEX` accepts a family). Modes, in order:

| Mode | What it can do | Limits |
|---|---|---|
| `cycles` | Re-runs with max cycles = failure cycle + margin: checks determinism, gives the tightest max cycles. Timeouts: max cycles = last retirement + `--hang-cycles`. | Needs an RVFI trace for timeouts. |
| `seeds` | Tries `--seeds` other seeds with the same memory timing; keeps the earliest failure. Each trial is capped at the best failure cycle + margin, so non-failing seeds stop early. | Only useful for random-timing failures. |
| `latency` | Tries fixed memory latencies and randomized timing with the best seed. | Same. |
| `symbols` | `--symbol NAME[:BYTES]`: binary search (0 included) for a smaller value of an integer in initialized data (an iteration count, a size) that still fails; writes patched ELF copies. Reports the smallest tested failing value (`smallest_failing`); the best ELF is the one with that value. `exact` is true only with `--monotone` (you vouch that the failure is monotone in the value) or `--exhaustive` (every untested smaller value is tried in ascending order within `--budget`); otherwise a `note` says how many smaller values were not tested. A trial that proves nothing (no result, or inconclusive by the shared rule: harness `error`, synthesized result, wall-clock timeout, C1 `inconclusive`) stops the search for that symbol. | The program must read the value from data, not an immediate. Without `:BYTES` the width is the symbol's size if it is 1, 2, 4 or 8 bytes; arrays and structs need `:BYTES` (the first element is shrunk). riscv-tests benchmarks such as `qsort` use compile-time sizes (`DATA_SIZE`), so they cannot be shrunk this way. |

Trials run in batches through the adapter's `run-many` (one JVM and one compiled model), falling back
to one `run` per trial. `--budget` caps the number of trials. A final `confirm` trial re-runs the best
reproduction with the tight max cycles. Output: `reduce.json`, `reduce.md`, one directory per trial.

What counts as a reproduction:

- The original run is checked first: a passing run, a signature that does not match `--signature`, a
  wall-clock timeout (`timeout:wall-clock`), or a timeout that its RVFI trace shows was still retiring
  (not a hang) is bad input (exit 2).
- A trial that ends in a wall-clock timeout (the adapter's `timeout:wall-clock` or rvw's own `--timeout`)
  never matches, not even through `re:`.
- A trial that passes never matches, not even through `re:.*` (bisect: a passing step is `good`).
- A trial that ends in `timeout` matches only if it is a hang: its RVFI trace shows no retirement in the
  last `--hang-cycles` cycles. When the target can be `timeout`, every trial asks for an RVFI trace, and
  a trial without one never matches. A re-run that only reached the lowered max-cycles cap is never a
  reproduction. The trace counts as evidence only when it is a C2 trace (header first), the lines read
  from its end parse with nondecreasing cycles, and it covers the end: a C2 `end` event at or after
  the run's last cycle (or a retirement inside the final interval, which proves "not a hang").
  Otherwise the trial is inconclusive (`conclusive: false`), so a symbol search stops there.
- `reduce.json` has `reproduced`; the CLI exits 1 when no trial matched (then the "best" run is the
  original one, and `reduce.md` says so).

### Instruction and interrupt reduction

```sh
rvw reduce RUN_DIR --modes instructions --instruction-symbol failing_loop --budget 64 --json
rvw reduce RUN_DIR --modes irq --budget 64 --json
```

`instructions` accepts a little-endian RISC-V ELF with a nonempty sized symbol
in an executable section. The symbol must contain only 16-bit or 32-bit
instructions. Use `.type NAME,@function` and `.size NAME,.-NAME` in assembly.
The reducer replaces removed instructions with same-size NOPs. It preserves
addresses, branch offsets, data, and all bytes outside the symbol. It does not
relocate code. Keep setup, trap handlers, and required exit code outside the
selected symbol. Repeat `--instruction-symbol` to reduce more than one symbol.
This mode is separate from integer data reduction with `--symbol`.

`irq` reduces the inline `--irq-schedule` from the saved replay. It removes
full-level events. It keeps the first event, the original cycle values, event
order, ELF, seed, memory timing, and other replay options. It never removes the
schedule option, which would enable device-generated interrupts. Event removal
can extend a prior level until the next event. Use this mode only when that is a
valid environment. Required transactions, multi-hart inputs, and arbitrary device
schedules are not supported in this increment.

Both modes first rerun the unchanged input. Each candidate runs through the
same conclusive failure-signature and hang checks as the other modes. A new
wall timeout or harness error cannot reproduce the failure. An inconclusive
candidate stops the search. Each accepted removal starts from the last confirmed
candidate, even if the failure occurs later. The saved best replay uses that input.

Chunk removal uses delta debugging. `streams` records retained instruction or
event indices and completion for each search. `one_minimal: true` means that no
single remaining item can be removed under the tested predicate at that stage.
It does not prove a global minimum. `budget_exhausted` and `inconclusive` stop
reasons never claim local minimality. All trials, including initial confirmation,
count against `--budget`. Later modes can change the search context.

## rvw bisect

Finds the first core commit with the failure signature. It never touches the shared checkout: it makes
a private `git clone --shared` in a workspace, checks the endpoints (bad must match, good must pass),
then drives `git bisect` one step at a time, running the run's adapter command with the core-source
variable (`[core].source_env`, BOOM `SPINAL_BOOM`) pointing at the clone. Signature match → bad,
pass → good, a wall-clock timeout (`timeout:wall-clock` or rvw's `--timeout`) → always skip, anything
else (build failure, a different failure) → skip (`--other good|bad` to change). A run or `--signature`
that is itself `timeout:wall-clock` is refused (exit 2). A `timeout` counts as the signature only with
hang evidence from an RVFI trace (`--hang-cycles`, as in `rvw reduce`); a `timeout` whose trace is
not evidence (see above) is skip, whatever `--other` says. Reports the first bad commit with its message and
diffstat, or the set of candidates when skipped commits hide it. Output: `bisect.json`, `bisect.md`,
one run directory per step.

Workspace safety:

- The default workspace is a new, uniquely named directory under `~/.cache/rvw/bisect/`. It is locked
  (`flock`) while the bisect runs, so two bisects never share one.
- An existing `--workdir` is used only if it is a real directory (not a link) with this tool's marker
  (`.rvw-bisect.json`, same origin) and its own clone of that origin. Anything else is refused.
- Every git command on the clone names `--git-dir` and `--work-tree`, after a check that the clone is
  a real directory with its own `.git`, its own top level and the origin as `remote.origin.url`.
- `--remove-clone` deletes the clone only if this invocation created it.

Max cycles of each step: `--max-cycles`, else the unreduced run's max cycles when `RUN_DIR` is a
trial directory of `rvw reduce` (found through `../reduce.json`), else the run's own. A reduced run's
tight max cycles would stop a good revision before the program ends. If the good endpoint times out,
the error says to pass a larger `--max-cycles`.

A reduced run (`rvw reduce`) helps when it found an earlier-failing seed or latency: bad steps then
stop at the earlier failure. Good steps still run the program to its end. For BOOM every step
rebuilds the Verilator model, so expect minutes per step for `small` and much more for `large`.

## Core debug description (`RiscvSim/<core>/debug.toml`)

Found through `--core-config`, `$RVW_CORE_CONFIG`, or `RiscvSim/<result.core>/debug.toml`. Patterns are
Python regexes over dotted VCD names (`TOP.BoomSimTop.tile.lsu_1.ldq_valid_3`).

```toml
[core]
name = "boom"
clock = 'TOP\.BoomSimTop\.clk$'
period = 10                       # wave time units per cycle
source_env = "SPINAL_BOOM"        # adapter's core-source variable (rvw bisect)
commit = 'TOP\.BoomSimTop\.tile\.core\.rob_1\.io_commit_valids_\d+$'   # RVFI skew measurement (optional)

[failure]
units = { 'lsu\.scala' = "LSU" }                 # assertion file -> unit
insn_units = { load = "LSU / D$", fp = "FPU" }   # oldest unretired instruction class -> unit (hangs)

[[snapshot]]                      # one group per unit
name = "Load queue"
unit = "LSU"
scope = 'TOP\.BoomSimTop\.tile\.lsu_1\.'          # fields match the rest of the name, whole
values = { head = 'ldq_head', tail = 'ldq_tail' }
enums = { state = ["reset", "normal"] }           # labels for values
counts = { valid = 'ldq_valid_\d+' }              # 1-bit signals that are 1
busy = { mshrs = { pattern = 'mshrs_\d+\.state', idle = 0 } }   # signals != idle
[snapshot.table]                  # rows: entries whose key is 1 (idle = N: key != N; all = true)
key = 'ldq_valid_(\d+)'
columns = { pc = 'ldq_uop_(\d+)_debug_pc', executed = 'ldq_executed_(\d+)' }

[handshakes]
scope = 'TOP\.BoomSimTop\.'
clock = 'clk'
requests = ["a", "c"]
responses = ["d"]
opens = { c = [6, 7] }                             # optional: request opcodes that expect a response
closes = { d = { a = [0, 1, 2, 4, 5], c = [6] } } # optional: response opcodes that answer each request channel
[handshakes.channels]
a = { valid = 'io_mem_a_valid', ready = 'io_mem_a_ready', id = 'io_mem_a_payload_source', opcode = 'io_mem_a_payload_opcode', info = 'io_mem_a_payload_address' }
c = { valid = 'io_mem_c_valid', ready = 'io_mem_c_ready', id = 'io_mem_c_payload_source', opcode = 'io_mem_c_payload_opcode' }
d = { valid = 'io_mem_d_valid', ready = 'io_mem_d_ready', id = 'io_mem_d_payload_source', opcode = 'io_mem_d_payload_opcode' }

[spinaltrace]
top_module = "BoomSimTop"
extra_scopes = ["TOP", "BoomSimTop"]
# pdg = "/path/to/pdg.json"       # if the adapter does not record a 'pdg' artifact
# criteria = { timeout = "signal:tile.core.rob_1.rob_head" }   # criterion for failures without an assertion
```

To add a core: run one wave build, `rvw wave list wave.vcd 'rob|lsu|...'` to find the names, and write
the groups. The generic code needs no change.

## MCP tools

`rvw mcp` discovers `bundle_make`, `reduce_run` and `bisect_run`. Their arguments use the CLI
option names with underscores (`run_dir`, `no_rerun`, `core_repo`); `modes` and `latencies` are
comma-separated strings, and `symbol` is an array. They return a `job_id` immediately. Use
`job_status(job_id, wait_s=60)` for the result, `job_log` for progress, and `job_cancel` to stop
the worker and its subprocesses. Results match the CLI's `--json`; adapter re-runs retain the
core lock and bisect uses a private clone.

Waveforms are exposed as `wave_info`, `wave_list`, `wave_changes`, `wave_sample` and `wave_cut`.
The first four are annotated read-only. `wave_cut` writes `out`. Time arguments `t0`, `t1` and
`at` are strings in wave units or cycle notation (`"20c"`), using `period` or clock detection;
`wave_sample` also accepts `at="end"`. Use `regex` and `limit` to narrow change queries.

## Tests

`rvw/tests/test_debug_tools.py` drives all three tools through `rvw/tests/fake_debug_adapter.py`, a
C1 adapter whose "bug" depends on seed, memory latency and a file in a fake core repo (plus modes for
hangs, a data symbol, a reset offset and an RVFI stamp skew). `rvw/tests/test_debug_runs.py` covers the
re-run layer (fresh attempt directories, process-tree timeouts, replay paths, C1 loading).
The model flag `--spinaltrace` selects dependency-trace instrumentation.

## Decisions

- Capture the C1 result, declared artifacts, conventional wave/trace/log artifacts, debug
  config, PDG and ELF before reading them. A declared missing artifact refuses the command.
  Require the captured ELF hash to match C1 `elf_sha256`. Use that copy for disassembly,
  trials, symbol patches and saved replays. Reports preserve the original paths as provenance.
- Capture core and adapter source trees before trials. An adapter outside a captured tree
  uses its directory as the dependency root. Keep sibling modules and their relative paths.
  Git roots use the Git file list. Other roots include all entries. External dependencies
  need a captured source root or an installed package. Source files stay read-only;
  directories permit private build outputs. Set `PYTHONDONTWRITEBYTECODE=1` for adapters.
- Keep capture-time hashes for provenance. Check private source stat stamps after adapter
  execution, before a trial counts as a match, and before publication. Changed inputs refuse
  the result. Keep launcher descriptors and source bindings with saved replays. Debug capture
  does not prove a clean Git tree, so its source descriptor keeps `core_dirty: true`.
- Keep unique input directories under `~/.cache/rvw/debug-inputs` while reports or replays
  need them. Staging stays outside the input trees. Output can be inside a checkout or a
  read-only archive's separate output directory. The standalone `snapshot_elf` API keeps
  its `input-<sha256>.elf` compatibility name and refuses conflicting files or symlinks.
- Resolve adapters and interpreters in the replay's child environment. Apply `env -u`
  removals before assignments. An unset `PATH` uses the system default search path.
  `RVW_PYTHON` and `RVW_LOCK_PYTHON` use rvw's interpreter. The shared interpreter binder
  preserves a Python venv's launcher, config hash and package inventory. Installed packages
  stay stable under C8. A changed venv config refuses publication.
- Use the shared shebang parser for debug, regress and wave tools. Direct interpreters can
  have one argument, such as `/bin/bash -e`. Plain `/usr/bin/env bash` is supported.
  Other `env` forms, including `env -S`, refuse capture. C1 adapters need no `--version`.
- ELF, source, artifact and tool identities come from capture records. Arbitrary adapters
  can read undeclared dependencies, so debug caching stays disabled (`cache_key: null`).
  Reports do not claim complete dependencies for arbitrary build scripts.
- With `--no-rerun --no-spinaltrace`, bundle uses saved artifacts and the verified ELF.
  It does not require the historical adapter or source checkout. It sets `replay` to null
  and publishes no `replay.sh`. An archive report does not establish a fresh reproduction.
- Publish a complete immutable report generation through one `current` pointer. Root files
  are compatibility views, not an atomic result set. Machine readers use `open_current`.
  Keep partial progress separate from a completed generation.
- Resolve bisect good and bad names once to full commit IDs. Use a private clone with its own
  objects and no alternates. Clean build output before each checkout. Capture each tested
  revision separately. Record the tested source and replay. `replay_tested` is false when
  `--no-verify` lets Git infer an endpoint that was not run.
- Every rerun uses a fresh directory. Reject an old copied result. A wall-clock timeout,
  harness error, synthesized result or other shared inconclusive cause cannot reproduce
  or rule out a failure. Pass and wall-clock signatures never match a user pattern.
  Adopt an ordinary rerun's cycle mapping when it reproduces. A SpinalTrace rerun must also
  fail at the same cycle because its wave window is narrow.
- A timeout proves a hang only with valid C2 evidence that covers the final interval.
  Read back through trailing events to a retirement or the start. Require a C2 header,
  valid cycle order, and either a recent retirement or a complete end event. Missing or
  truncated evidence stays undetermined. `hang_cycles` must be a positive integer.
- Confirm the original symbol value before searching smaller values. A failed confirmation,
  inconclusive trial or exhausted budget gives `smallest_failing: null` and `exact: false`.
  Binary search reports the smallest tested failing value. It proves the minimum only with
  a declared monotone failure or a complete exhaustive search. Symbol metadata cannot
  replace C1 run fields. Only integer data symbols are reduced. Without `:BYTES`, accept
  only 1, 2, 4 or 8 byte symbols. Instruction reduction uses sized executable ELF symbols and NOP replacement.
- Derive snapshots from VCD/FST. A covering wave must reach the failing cycle's edge and
  have a known cycle mapping. Otherwise rerun or label the snapshot with its actual end.
  Unknown values cannot prove an empty queue, stall, fire or completed request. Collect
  all fires on an edge before closing older requests and adding new ones. Unknown response
  opcodes keep requests open. This can overreport open requests for zero-latency protocols.
- Adapter timeouts start after the resource lock is held. Forward the lock descriptor for
  nested builds. Cancellation stops process groups, including separate adapter groups.
  Progress goes to stderr. JSON stdout contains one complete strict JSON document.
- Fixture tests establish tool behavior. They do not establish BOOM or hardware behavior.

## Demonstration: the LSU assertion at `lsu.scala:1241` (BOOM `large`, qsort, randomized timing)

Core `spinal-boom-eda` @ 0cb0b69, ELF `spinal-boom/gem5/bench/build/bare/qsort.riscv`.

These saved observations predate the current C3 signature format, explicit wave
clock, RVFI skew report and stricter reduce rules. They were not regenerated.
They describe a known core failure and do not validate the current bundle flow.

1. Reproduce: seeds 1-4 pass (about 290k cycles each). The seed recorded by the cycle-equivalence
   harness (`docs/CYCLE_EQUIVALENCE.md` in spinal-boom-harness: case seed 975830445) fails:
   `RiscvSim/boom/run.sh run --elf qsort.riscv --config large --seed 975830445` →
   `assert` at cycle 50,087, `FAILURE lsu:L1241 (lsu.scala:L1241)`, 177 s.
2. `rvw bundle` (931 s, nearly all of it the two re-runs): the RVFI+wave model and the
   SpinalTrace-instrumented model both reproduce the failure at exactly cycle 50,087. A second bundle
   from the re-run directory, with the PDG and instrumented wave already there, takes 57 s.
3. `rvw reduce` (12 trials, 593 s, four at a time through `run-many`): max cycles 400,000 → 50,187.
   Seeds 1-8 do not fail within that bound, and neither do fixed latencies 1, 5 or 20. The failure
   needs the memory agent's random probes, which fixed-latency mode turns off.

What the bundle says:

- Last retirement at cycle 50,075, inside `verify.constprop.0` (qsort's result check): four `lw` per
  iteration through two pointers that are equal (`a4 == a5`), so pairs of loads hit the same word.
- Snapshot: the load queue is full (24/24). Entries 3 (`lw a3,4(a4)`, older) and 4 (`lw a6,4(a5)`,
  younger) both target `0x8000588c`. Entry 4 is executed, succeeded and observed; entry 3 is not
  executed. MSHR 3 is refilling line `0x80005880`.
- Dependency trace (criterion: the `when` at `lsu.scala:1239` that guards the assert): the search is
  a **load wakeup** (`fired_load_wakeup_0 = 1`) of LDQ entry 3 at `0x8000588c`. It matched entry 4
  (`lcam_younger_load_mask_0_4 = 1`), which was `executed && succeeded && observed`.
- Wave history (`rvw wave changes`): the younger load executes at 50,054. In the same cycle the memory
  agent probes the line (B `Probe toB`, `0x80005880`). The older load is nacked at 50,056 because the
  line is being refilled. The D$ answers the probe at 50,060, which sets `observed` on both entries.
  The younger load succeeds at 50,075. The older load is woken up again at 50,084, its search finds
  the younger one, and the assertion fires.

Note on cycles: the retirement cycles above are RVFI stamps, 2 cycles after the commit in the wave
(measured on this run's wave, see "RVFI stamps and the wave").

What the wave shows, and what it does not:

- The wave confirms the sequence above, and that the probe race is legal: TileLink allows a probe at
  any time, and the stress memory agent sends one between the younger load's execution and the older
  load's nacked replay.
- In this instance the younger load got its data after the probe was answered, so it returned the
  current value. The wave shows **no ordering violation**: the assertion fires on the situation, not on
  wrong data.
- Cause of the assertion: this is upstream BOOM v4's own `assert(false.B)`. Upstream commented out the
  load-load ordering-failure handling (`ldq_order_fail` / `failed_load`) and asserts that "an older
  search gets replayed and finds a younger search already released" can no longer happen. The probe
  race above makes it happen, so the port is faithful and the upstream assumption is too strong.
- "Turning the assertion off would allow a same-address load-load (CoRR) ordering violation" is an
  argument, not a demonstrated result: it holds if a store from another agent changes the line between
  the two loads' data returns, which this run does not show. Restoring the order-failure replay of the
  younger load is the likely fix, but that is a decision for the core, not made here.

## Limit ownership

Real-history bisect validation: [#45](https://github.com/riscPrint/risc-v-workstation/issues/45). Dependency-model parity: [#68](https://github.com/riscPrint/risc-v-workstation/issues/68). Integrated debug: [#24](https://github.com/riscPrint/risc-v-workstation/issues/24).

Retained limit: Cause traces require suitable waves, a matching graph and a bounded window. A partial bundle does not prove a root cause.

### Historical adapter limits

A source revision can predate the current adapter API. A failed build is a skipped
endpoint. The result marks it `inconclusive: true`. It does not identify a guilty
commit. Use a compatible adapter before repeating the comparison. Do not use
`--no-verify` to turn an untested endpoint into evidence.

Debug reruns refuse conclusive evidence when the returned C1 seed, config,
max_cycles or mem_latency differs from an explicitly requested value.
This rule applies to bundle, reduce and bisect, including run-many batches.

Debug reruns also require the returned `elf_sha256` to match the requested ELF bytes.
A missing or different hash makes the attempt inconclusive.
