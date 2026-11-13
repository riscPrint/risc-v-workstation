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
