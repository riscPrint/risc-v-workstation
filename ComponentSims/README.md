# Native component simulators

Trace-driven models of the parts of a core front end and memory system, in the
class of ChampSim and the CBP frameworks. Use them to choose predictor, BTB,
cache and prefetcher designs from data before RTL work. They do not model a full
core. The OoO timing model (`rvw ooo`) can call them in process through
`rvw.csim.lib`.

| Area | Models |
|------|--------|
| Direction | bimodal, gshare, local (two-level), tournament (21264 style), perceptron, hashed perceptron / GEHL, TAGE, L-TAGE, TAGE-SC-L, always-taken, BTFN, perfect bound |
| Targets | multi-level set-associative BTB with partial tags and level latencies; RAS with `none`, `pointer`, `pointer_top` and `full` repair; indirect targets from the BTB or ITTAGE |
| Front end | decoupled BPU → FTQ → I-cache → decode delivery model with FDIP, BTB level bubbles, decode and execute redirects, wrong-path I-cache fetch |
| Caches | L1I, L1D, L2, LLC; LRU, random, tree PLRU, SRRIP, BRRIP, DRRIP, SHiP, Hawkeye, Belady OPT bound (L1D); perfect level |
| Prefetchers | next-line, IP-stride, stream, BOP, SPP, SMS, Berti (data); EIP and FDIP (instruction) |
| Translation | L1/L2 TLB, radix page walks with per-level page walk caches, walks through the data cache |
| Other | memory dependence (store sets, wait table, always/never speculate, perfect); value prediction (last value, stride, VTAGE); move and zero-idiom counts |

Every model is our own implementation from the published papers (see the header
of each file in `include/csim/`). No ChampSim, CBP or gem5 code is copied.
The models follow the paper structure, not any reference bit for bit.

## Use

```sh
rvw csim models                                   # models and study keys
rvw csim run STUDY.json TRACE... [--set KEY=VALUE] [--json]
rvw csim sweep STUDY.json TRACE... --param branch.max_history=320,640 \
    --param branch.table_entries=1024,2048 --budget-kib 64 --metric direction_mpki
rvw csim budget STUDY.json                        # storage per table, no trace
rvw csim convert c2 rvfi.jsonl --out t.csim [--values]
rvw csim convert bt9 trace.bt9.gz --out t.csim
rvw csim compare-rtl STUDY.json --trace rvfi.jsonl --events EVENTS
rvw csim build                                    # engine and library paths
```

The same operations are MCP tools: `csim_run`, `csim_sweep`, `csim_budget`,
`csim_models`, `csim_convert` and `csim_compare_rtl`.
The first `rvw` call compiles the engine with the system C++17 compiler into
`~/.cache/rvw/csim/<source hash>/` (`RVW_CSIM_CACHE` changes the place).

Traces: C2 `rvfi.jsonl` (converted on the fly), CBP 2016 BT9 text (`.gz`/`.xz`
allowed), ChampSim binary traces (`.xz`/`.gz` allowed; read by the engine), the
native `rvw.csim-trace/1` and the legacy `rvw.branch-trace/1`. `--format auto`
detects the format from the content.

A study file (`rvw.csim-study/1`) is JSON. Each section configures one component:
`branch`, `btb`, `ras`, `indirect`, `wrong_path`, `frontend`, `memory`, `mdp`,
`vp`, `report`, plus `warmup_instructions` and `simulation_instructions`. The
engine refuses keys that no model reads. `source` holds provenance and the list
of approximations. Its `fidelity` can only be `approximate` or `unqualified`.
Examples: [`examples/wide-core.json`](examples/wide-core.json) (illustrative wide
core) and [`examples/boom/csim/tage-l.json`](../examples/boom/csim/tage-l.json)
(BOOM TAGE-L sizes, with the differences listed).

A project describes its own predictor with data: TAGE `tables` give entries,
history length and tag width per table; `loop` and `sc` give the loop predictor
and statistical corrector; `btb.levels` gives a BTB hierarchy. Sweeps change any
dotted key. Rows outside the storage budget are marked, not dropped. Points that
the engine refuses carry an `error` and do not stop the sweep.

Reports keep each trace apart. The aggregate is the arithmetic mean of per-trace
values and says so. Storage is in bits per table (`storage`), with
`metadata_kib` (without cache data arrays) for predictor budgets.

## Library interface

```python
from rvw.csim.lib import Components
c = Components({"branch": {"model": "tage-sc-l"}, "btb": {"entries": 4096},
                "ras": {"entries": 32}, "memory": {"l1d": {"size_kib": 48, "ways": 12}}})
ticket, taken = c.predict(pc)            # direction prediction
c.history(pc, "cond", actual, target)    # actual-path history update
c.update(ticket, actual)                 # train now or later
level, target = c.btb_lookup(pc); c.btb_update(pc, "cond", actual, target)
done = c.access(cycle, pc, addr)         # completion cycle of a data access
```

The C ABI is in `capi.cc` (`csim_create`, `csim_dir_predict`, ...). Tickets
allow delayed and out-of-order training. Histories follow the actual path.

## RTL comparison

`compare-rtl` runs the model on the C2 trace of one RTL run and aligns it with
explicit predictor events from the same run: `rvw.bp-events/1` JSONL from a
project probe binding, or Kanata `#rvw 1 prediction` records. It reports
per-branch disagreement, RTL and model misses and agreement. It needs the ELF
hash on both sides, a single hart, the counter semantics and an event for every
conditional branch in the ROI. If any is missing, the status is `inconclusive`.
A Kanata log also gives retirement-inferred redirects in a separate `inferred`
section. No result is a match or fidelity verdict.

## Decisions

- One native C++17 engine, header-only models, no libraries. Python only
  converts, sweeps and reports. The engine streams the trace, except for Belady
  OPT, which buffers it to compute next uses.
- Training is sequential on the actual path. Prediction comes before training.
  `branch.update_delay` delays training by N branches; histories stay exact.
- Wrong paths come from a learned control-flow graph: after an execute redirect
  the model walks the blocks seen so far (`wrong_path.branches`) for RAS effects,
  and the front end fetches them into the I-cache (`frontend.wrong_path_icache`).
- Memory timing is approximate: access time is `ordinal * cycles_per_instruction`
  and a miss completes after the level latencies. Prefetch timeliness, late
  prefetches and the per-level prefetch queue use these cycles. Demand misses
  have no MSHR or bandwidth limit.
- The front-end model gives a delivery bound with a back end that never stalls.
  Bubble categories can overlap.
- The memory dependence model has no timing: every older store inside
  `unresolved_window` instructions is unresolved when the load issues.
- RISC-V call and return classes follow the return-address hints (x1/x5). A
  coroutine swap counts as a push. ChampSim call sizes are learned at returns.

## Limits

- No model is qualified against a pinned independent reference on published
  traces yet. Tests check hand-derived cases, a scalar perceptron reference and
  the legacy bimodal/gshare engine. MPKI numbers are for comparison between
  models on the same traces, not for RTL claims.
- BOOM settings are approximate (see the study file). No RTL fidelity claim.
- No SMT, no multi-hart traces, no ROI sampling weights (SimPoint) yet.
- The BT9 reader follows the published format description; it has not been run
  on the CBP 2016 trace set here. ChampSim branch types follow the documented
  register rules.
- No native RTL comparison has run yet: no adapter writes `rvw.bp-events/1`.
- MPKI and miss counts do not give IPC or speedup.

## Tests

```sh
rvw/.venv/bin/python -m pytest ComponentSims/tests -q          # engine (compiles it)
rvw/.venv/bin/python -m pytest rvw/tests/test_csim_formats.py rvw/tests/test_csim.py -q
```

## Legacy branch engine and Spike input

`branch_sim.cc` is the first bimodal/gshare engine (`rvw.branch-trace/1` in,
`rvw.branch-sim/1` out). It stays as an independent reference for the new engine.

```sh
c++ -std=c++17 -O2 -Wall -Wextra -Werror ComponentSims/branch_sim.cc -o /tmp/branch-sim
/tmp/branch-sim gshare 4096 12 1 0 < trace.txt
python3 ComponentSims/spike.py --verify verify.json --workload crc32 --engine /tmp/branch-sim \
  --out /path/to/study --model gshare --entries 4096 --history 12 --pc-shift 1 --warmup 0
```

The Spike adapter reads one successful `rvw workloads verify --trace` row,
checks the evidence hashes and writes `trace.txt` and `report.json`. Its
`trace.txt` is also valid input for `rvw csim run` (direction models only).
