# C5. Failure bundle (`rvw bundle`)

`rvw bundle RUN_DIR [--out DIR]` turns a failed run (C1 result) into a directory:

```
summary.md       for a reader: what failed, where, last progress, suspected unit, next commands
summary.json     the same, structured (schema "rvw.bundle/1")
retired.txt      last N retired instructions, disassembled
wave-window.vcd  waveform cut to a window around the failure (when a wave exists or can be re-run)
dynpdg.json      SpinalTrace dependency trace of the failing signal (when available)
replay.sh        exact command to reproduce (when replay inputs were captured)
```

With `--no-rerun --no-spinaltrace`, the bundle reads saved artifacts and the verified ELF.
It does not require the replay source or adapter. Its summary sets `replay` to null, gives a note
that replay is unavailable and omits `files.replay`. Its published generation has no `replay.sh`.

Cycle labels in a bundle use the run's `details.wave_time_of_cycle_1` and `details.wave_time_per_cycle`
(cycle N at `time_of_cycle_1 + (N - 1) × period`) and `details.wave_window`. An adapter that writes waves
should record them; without `wave_time_of_cycle_1` the bundle does not trust a wave to reach the failure
and says that its cycle labels are assumed. Details: `rvw/src/rvw/bundle/README.md`.

Snapshot counts use `?/N` when any input is unknown or absent. A snapshot table can include
`unknown_entries`, a list of `{"#": index, "value": value}` keys whose live state is unknown.
An empty `rows` list with unknown entries does not prove that the table is empty.

### Reduction and bisect reports

`rvw.reduce/1` adds `streams`, keyed by `instructions:SYMBOL`, `irq`, or `stimulus`.
For `stimulus`, `kept` contains group names, and counts refer to groups.
The replay must include `--stimulus-file`; C1 must record its `stimulus_sha256`.
The `rvw.stimulus/1` event format and dependency rules are defined in
`rvw/src/rvw/bundle/README.md`. Minimality applies to admissible group removals.
Each entry has `original`, `remaining`, `kept` (zero-based input indices),
`completion`, `one_minimal`, and `global_minimum` (always false).
IRQ indices exclude the fixed initial event from the search, but still refer to
the full original schedule. Completion is `one_minimal`, `initial_not_reproduced`,
`inconclusive`, or `budget_exhausted`. `one_minimal` applies only to that search's
context. It proves no global minimum. Top-level `budget_exhausted` reports whether
the trial count reached the configured limit. The best replay includes the
captured candidate ELF and the reduced inline schedule. Every candidate uses the
shared conclusive reproduction rules. Integer data reduction stays in `symbols`.

`rvw.bisect/1` marks `result.inconclusive: true` when endpoint verification
stops on a skipped run. It cannot publish `first_bad` for that result.
