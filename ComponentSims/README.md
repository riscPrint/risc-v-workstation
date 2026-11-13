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
| Front end | decoupled BPU → FTQ → I-cache → decode delivery model with FDIP, BTB level bubbles, decode and execute redirects, wrong-path I-cache fetch, micro-op cache |
| Caches | L1I, L1D, L2, LLC; LRU, random, tree PLRU, SRRIP, BRRIP, DRRIP, SHiP, Hawkeye, Mockingjay, Belady OPT bound (L1D); perfect level |
| Prefetchers | next-line, IP-stride, stream, BOP, SPP, SMS, Bingo, IPCP, Berti (data); EIP and FDIP (instruction) |
| Translation | L1/L2 TLB, radix page walks with per-level page walk caches, walks through the data cache |
| Other | memory dependence (store sets, wait table, always/never speculate, perfect); value prediction (last value, stride, VTAGE); load address prediction (last address, stride, context); move and zero-idiom counts |

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
rvw csim compare BASE.json CANDIDATE.json [--tolerance 0.02]   # per-trace deltas of two run reports
rvw csim convert c2 rvfi.jsonl --out t.csim [--values]
rvw csim convert bt9 trace.bt9.gz --out t.csim
rvw csim compare-rtl STUDY.json --trace rvfi.jsonl --events EVENTS
rvw csim qualify TRACE... [--reference cbp2016-tage-sc-l-64kb|cbp2016-tage-sc-l-8kb]
rvw csim convert spike spike.log --out t.csim     # spike -l --log-commits ELF 2> spike.log
rvw csim simpoint TRACE --interval 10000000 --out points.json   # weighted simulation points
rvw csim run-points STUDY.json TRACE --points points.json --warmup 50000000
rvw csim build                                    # engine and library paths
```

The same operations are MCP tools: `csim_run`, `csim_sweep`, `csim_budget`,
`csim_models`, `csim_convert`, `csim_qualify`, `csim_simpoint`, `csim_run_points`,
`csim_compare` and `csim_compare_rtl`.
The first `rvw` call compiles the engine with the system C++17 compiler into
`~/.cache/rvw/csim/<source hash>/` (`RVW_CSIM_CACHE` changes the place).

Traces: C2 `rvfi.jsonl` and Spike `-l --log-commits` logs (converted on the fly), CBP 2016 BT9 text (`.gz`/`.xz`
allowed), ChampSim binary traces (`.xz`/`.gz` allowed; read by the engine), the
native `rvw.csim-trace/1` and the legacy `rvw.branch-trace/1`. `--format auto`
detects the format from the content.

A study file (`rvw.csim-study/1`) is JSON. Each section configures one component:
`branch`, `btb`, `ras`, `indirect`, `wrong_path`, `frontend`, `memory`, `mdp`,
`vp`, `lap`, `report`, plus `warmup_instructions` and `simulation_instructions`. The
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

## Sampled simulation

`rvw csim simpoint` cuts a trace into fixed instruction intervals, builds a
basic-block vector per interval, projects it to 15 random dimensions and runs
k-means for k = 1..`--max-k`. It keeps the smallest k whose BIC reaches 90% of
the observed BIC range (the SimPoint rule). Each cluster gives the interval
nearest its centre and a weight (its share of instructions).
`rvw csim run-points` runs a study on each point (`skip_instructions` fast
forwards without state changes, `--warmup` instructions train state, the point
is measured) and reports weighted metrics. It does not estimate sampling
error. Check a few workloads against a full run first: on the qsort trace above,
10 points at a 10 000-instruction interval give 43.6 MPKI against 42.1.

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

## Qualification against a pinned reference

`rvw csim qualify` runs an external reference predictor and a csim study on the
same traces. The references are the CBP-5 (2016) TAGE-SC-L 64 KB and 8 KB
predictors by A. Seznec (`AndreSeznecLimited.tar.gz` from jilp.org, sha256
`5ed93324…ace181`). The archive is fetched into the csim cache and checked
against the pinned hash. It never enters this repository. Our harness
(`qualify/ref_harness.cc`) and type shim (`qualify/shim/`) build it. The harness
allocates the predictor on the heap. One guard is added to the cached copy: `if (NOSKIP[i])` becomes
`if (i <= NHIST && NOSKIP[i])`. The upstream allocation loop reads one entry
past the arrays (AddressSanitizer, 8 KB predictor); in-range accesses do not
change. The report records the patch.

Matched studies: [`examples/tage-sc-l-64kb.json`](examples/tage-sc-l-64kb.json)
(63.8 KiB) and [`examples/tage-sc-l-8kb.json`](examples/tage-sc-l-8kb.json)
(8.5 KiB). Their `source.approximations` list the structural differences.
Both models train at once on the actual path with no warmup.

Results on 2026-11-13 (Spike traces of the riscv-tests benchmarks built by
`rvw arch build`, whole program, `--isa=rv64gc_zba_zbb_zbs_zicntr`). MPKI is
conditional direction misses per 1000 instructions. Agreement is the fraction
of conditional branches where both predict the same direction. All rows are
within the default 10% relative MPKI tolerance.

| Size | Trace | Conditional | Reference MPKI | csim MPKI | Agreement |
|------|-------|------------:|---------------:|----------:|----------:|
| 64 KB | qsort | 61124 | 40.86 | 42.08 | 0.924 |
| 64 KB | dhrystone | 28379 | 0.30 | 0.27 | 1.000 |
| 64 KB | median | 3132 | 22.73 | 23.93 | 0.941 |
| 64 KB | rsort | 17601 | 0.20 | 0.21 | 0.999 |
| 64 KB | towers | 459 | 9.00 | 9.50 | 0.924 |
| 64 KB | spmv | 6288 | 14.83 | 16.09 | 0.900 |
| 8 KB | qsort | 61124 | 41.01 | 41.92 | 0.925 |
| 8 KB | dhrystone | 28379 | 0.32 | 0.27 | 0.999 |
| 8 KB | median | 3132 | 25.20 | 23.93 | 0.930 |
| 8 KB | rsort | 17601 | 0.22 | 0.22 | 0.999 |
| 8 KB | towers | 459 | 9.50 | 10.10 | 0.917 |
| 8 KB | spmv | 6288 | 17.25 | 18.18 | 0.894 |

More pinned references from the same competition build with the harness
(`--reference`): `cbp2016-mpp-64kb`, `cbp2016-mpp-8kb` and
`cbp2016-mpp-unlimited` (D. A. Jiménez, multiperspective perceptron),
`cbp2016-mpp-tage-64kb` (multiperspective perceptron with TAGE) and
`cbp2016-pruett-64kb`. They have no matched csim study; name one with `--study`.
Seznec's unlimited predictor stops on its own assertion with this harness and is
not listed. Direction MPKI on the same six traces (reference / csim):

| Trace | MPP 64 KB / csim hashed perceptron 64 KB | MPP unlimited / csim TAGE-SC-L 64 KB |
|-------|------------------------------------------|--------------------------------------|
| qsort | 40.90 / 41.75 | 40.56 / 42.08 |
| dhrystone | 0.35 / 0.36 | 0.36 / 0.27 |
| median | 21.27 / 20.80 | 21.40 / 23.93 |
| rsort | 0.29 / 0.27 | 0.29 / 0.21 |
| towers | 11.60 / 10.60 | 11.60 / 9.50 |
| spmv | 13.02 / 12.46 | 12.57 / 16.09 |

[`examples/hashed-perceptron-64kb.json`](examples/hashed-perceptron-64kb.json) is
a budget-matched global hashed perceptron, not a structural match of the
multiperspective predictor.

These traces are short (0.2–0.23 M instructions) and small in branch
footprint. They qualify the model shape, not long-run behaviour. The CBP 2016
trace sets were not reachable from here (the hosting server did not answer).

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
- The micro-op cache (`frontend.op_cache`) keys lines by aligned fetch window
  (`window_bytes`). A window needs `ceil(ops / ops_per_line)` lines of one set;
  more than `max_lines_per_window` is uncacheable. A fetch group hits only when
  all its lines are present; it then skips the I-cache and legacy decode and
  delivers `op_width` ops per cycle. Each change between op-cache and legacy
  delivery costs `switch_penalty` cycles. One instruction counts as one op (no
  cracking or fusion). Context rows flush it by default; the trace has no
  `fence.i` events, so self-modifying code is out of scope.
- The memory dependence model has no timing: every older store inside
  `unresolved_window` instructions is unresolved when the load issues.
- Context rows (`X`) mark privilege-mode or address-space changes. The BTB can
  share entries, flush or tag them by context (`btb.context`); the RAS can flush
  (`ras.context`); TLBs and walk caches can flush or tag by ASID
  (`memory.tlb.context`). Direction predictors always share state.
- RISC-V call and return classes follow the return-address hints (x1/x5). A
  coroutine swap counts as a push. ChampSim call sizes are learned at returns.

## Limits

- TAGE-SC-L is qualified against the pinned CBP 2016 reference on short
  benchmark traces only (see above). Other models are checked by hand-derived
  cases, the legacy bimodal/gshare engine and separate scalar Python references
  (perceptron, set-associative LRU BTB, circular RAS, LRU and SRRIP caches;
  `tests/test_csim_reference.py`), which match exactly on random traces.
  MPKI numbers are for comparison between models on the same traces, not for
  RTL claims.
- BOOM settings are approximate (see the study file). No RTL fidelity claim.
- No SMT and no multi-hart traces. Simulation points use pure-Python k-means,
  sized for up to a few thousand intervals.
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

### Native OoO issue service

`capi.cc` exports `csim_ooo_service` for a native timing scheduler. It combines
issue-time branch prediction and actual-path training, or one data-memory
service request split at cache-line and page boundaries. The OoO adapter uses
this C entry point directly. It shares the same component handle, parameters
and statistics as `rvw.csim.lib.Components`. It does not add wrong-path
execution, speculative history repair or instruction-cache invalidation.
The call layout is defined in `docs/contracts/arch.md`.
