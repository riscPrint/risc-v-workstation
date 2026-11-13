# RTL benchmark campaign

`rvw.rtl-bench-settings/1` selects pinned workload IDs and project ISA, ABI,
RAM base and RAM size. The existing workload build report gains an optional
`target` object. An absent target preserves the RV64 build contract.
`rvw.rtl-bench/1` contains project/config identity, machine, UTC date and
one row per selected program. Each row has instructions, cycles, IPC,
status and repeated samples. IPC is null when the run did not pass its
self-check. Failed rows retain diagnostics. `deterministic` is null without
repetition and compares exact cycles and instructions with repetition.
Top-down fields use `rvw.topdown/1`. No formal benchmark score is implied.
Resume requires matching campaign inputs and ELF hashes. Reports are local
run output. They are not release or gate evidence.

Bounded variants set `bounded` in the settings. Their target records
`sort_size`, `spmv_rows`, `dhrystone_runs` and `runtime`. Expected results
remain tied to the selected pinned inputs. The build report records these
options and hashes the builder assets. Dhrystone's checked variant carries
`checker: printed-final-values`. The original unchecked variant cannot pass.
C1 `run-many` uses one worker with a separate `wall_timeout` per program.

`rvw.rtl-bench-compare/1` contains the union of both program sets. Each row
has an IPC delta and relative percent change when both IPC values are valid.
A `compared` row requires two or more identical passing samples on each side
and equal retired instruction counts. Otherwise it is inconclusive. The
noise check reads samples directly. Top-down deltas subtract compatible
commit-slot fractions. Different ELF hashes remain explicit.

Optional row `topdown_status: c1_checked` states that top-down retirements
match C1 instructions. This is separate from the embedded top-down report's
C2 `checked`/`unchecked` status. `lowest_ipc` lists at most three passing
programs with valid attribution, sorted by IPC. Its explanations name the
largest non-retiring slot class. These remain project-bound partitions.
The row can also retain the first sample's C1 `metrics` for ROI interpretation.
Benchmark probe captures select C1 `probe_mode: topdown`. They retain only
the five counter totals needed for the table. Full event capture remains
available through the existing C1 adapter commands.

The campaign saves its identity with `status: incomplete` before building or
launching a batch. Resume can reuse a completed passing C1 result after
validating its ELF hash, seed, config, limits and capture mode. An output
directory without a saved identity cannot resume. Unfinished programs run
again. Completed table rows remain unchanged.
