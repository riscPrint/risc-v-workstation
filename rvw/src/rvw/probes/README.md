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
`etrace-ingress` (`rvw debug etrace` encoder input CSV) and `interrupts` (an independent check
of C2 interrupt traps). Output files must be new. Exit 0 on success, 2 with a JSON error.

MCP tools: `probes_list`, `probes_summary`, `probes_convert`.

## Consumer matrix

`list` gives one row per consumer tool. `enabled`: the probes it needs exist. `missing`: the
row names the probe kind and fields to add. `unknown`: the design database has no probe meta
(for example the `hpm` selector); check an event stream. `no_converter`: the probes exist but
no writer exists yet (per-slot CSR state, fault sites).

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
- Prediction records in Kanata, C2 `mmu_walks` grouping and C2/2 `csr_snapshot` are not
  written yet.
