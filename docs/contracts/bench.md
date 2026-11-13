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
