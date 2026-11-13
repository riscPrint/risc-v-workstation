# rvw probes

Reads the probe event stream (`probe-events.jsonl`, `rvw.probe-events/1`) that RiscvSim
writes for `run --probes`, lists a design's probes, and writes each consumer tool's format.
The RTL API is [SpinalProbes](../../../../SpinalProbes/README.md). The format is in
[PLATFORM_CONTRACTS.md](../../../../docs/PLATFORM_CONTRACTS.md#probe-event-stream-rvwprobe-events1).

```sh
rvw probes list --db rvw/out/vex-probes.db           # probes in a design database, and consumer gaps
rvw probes list --events run/probe-events.jsonl --json
rvw probes summary run/probe-events.jsonl
rvw probes convert run/probe-events.jsonl --to bp-events --c2 run/rvfi.jsonl --out run/bp-events.jsonl
rvw probes convert run/probe-events.jsonl --to kanata --out run/probes.kanata
rvw probes convert run/probe-events.jsonl --to counts --c1 run/result.json --c2 run/rvfi.jsonl --out run/counts.json
```

Targets: `bp-events` (for `rvw csim compare-rtl`), `kanata` (for `rvw perf`), `cache` (RiscvSim
`CacheEventObserver`), `mmu` (`rvw.mmu-observations/1` for `rvw regress mmu report`),
`counts` (`rvw arch ooo-calibrate` RTL event counts), `hpm` (`rvw.hpm-bindings/1`),
`etrace-ingress` (`rvw debug etrace` encoder input CSV), `interrupts` (an independent check
of C2 interrupt traps), `bus` and `csr-writes` (independent checks of the data bus and CSR
write port against C2), `mmu-walks` (a copy of the C2 trace with `mmu_walks` records for
`rvw regress mmu report`) and `fault-sites` (a site list for `rvw fault plan --sites`).
Output files must be new. Exit 0 on success, 2 with a JSON error.

MCP tools: `probes_list`, `probes_summary`, `probes_convert`.

## Consumer matrix

`list` gives one row per consumer tool. `enabled`: the probes it needs exist. `missing`: the
row names the probe kind and fields to add. `unknown`: the design database has no probe meta
(for example the `hpm` selector); check an event stream. `no_converter`: the probes exist but
no writer exists yet (per-slot CSR state).

## Decisions

- Converters check what they can against C2. Branch events must match C2 branch retirements
  one to one, with the same PC and taken outcome. Any difference is an error, because a
  speculative or missed event would make a predictor comparison wrong.
- Counter totals come only from a complete stream (with the end record).
- Kanata IDs: a probe ID names one instruction from its first stage event to its retire or
  flush. Stage events are occupancy. The converter writes a stage change once.
- Database listing uses the stable wire names. It cannot see probe meta.

## Limits

- One hart. Rows are written for hart 0.
- `interrupts` compares causes in order; `consistent` is agreement of two sources, not a
  cosim result.
- Prediction records in Kanata and C2/2 `csr_snapshot` are not written yet.
- `mmu-walks` takes the walks the probe declares. A squashed speculative walk gives an extra
  record (a checker mismatch). Each record goes on the first retirement at or after its
  result cycle; a walk after the last retirement is reported as `unattached`.

## Check required bindings

`rvw probes check --events probe-events.jsonl` names missing stage, retire,
flush and stall kinds. Use `--require kind/name` repeatedly for exact bindings,
for example `--require flush/fetch --require flush/decode --require stall`.
The command returns 3 for missing probes. MCP `probes_check` returns the same
report. `present` means declared presence only; it does not establish correct
wiring, runtime activation or complete pipeline accounting.

`--validate` also checks the event stream against the contract, and `--c2 rvfi.jsonl`
(implies `--validate`) compares the probes that claim retired events with the run. Each
finding names the probe (`kind/name`), the check and the first cycle: for example a retire
probe that retires an ID no stage probe saw, a stage event after its retire (ID reuse), a
1-bit counter whose total differs from its active cycles, or a branch probe with more events
than C2 branch retirements (the probe is before the commit point). Exit 1 means violations.

The init stub includes both younger-slot flushes for a simple three-stage
pipeline. Its instruction IDs must follow actual pipeline slots. Stall probes
use measured cause signals. A core with no wait mechanism can tie those inputs
false. Do not infer a memory stall from an arbitrary cycle without retirement.
